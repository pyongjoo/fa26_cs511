#!/usr/bin/env python3
"""Print the LSM levels of a RocksDB database and the keys in each SST file.

Keys still sitting in the memtable are counted, but not listed: they are not
in a level until a flush. Open the database read-only, so this can run while
another process has the database open for writes.

    ./show_lsm.py /path/to/db

Requires rocksdict and cramjam:

    python3 -m venv .venv
    .venv/bin/pip install rocksdict cramjam
    ./show_lsm.py /path/to/db
"""

import argparse
import os
import struct
import sys

_root = os.path.dirname(os.path.abspath(__file__))
_venv_root = os.path.join(_root, ".venv")
_venv_python = os.path.join(_venv_root, "bin", "python3")
if (
    os.path.isfile(_venv_python)
    and os.access(_venv_python, os.X_OK)
    and os.path.realpath(sys.prefix) != os.path.realpath(_venv_root)
):
    os.execv(_venv_python, [_venv_python, *sys.argv])

try:
    from rocksdict import AccessType, Rdict
except ImportError:
    sys.exit(
        "This script needs the rocksdict and cramjam packages.\n"
        "  python3 -m venv .venv && .venv/bin/pip install rocksdict cramjam"
    )

try:
    import cramjam
except ImportError:
    sys.exit(
        "This script needs the cramjam package to decompress SST blocks.\n"
        "  python3 -m venv .venv && .venv/bin/pip install rocksdict cramjam"
    )


BLOCK_TRAILER_SIZE = 5
NEW_FOOTER_SIZE = 53
LEGACY_FOOTER_SIZE = 48
BLOCK_BASED_MAGIC = 0x88E241B785F4CFF7
LEGACY_BLOCK_BASED_MAGIC = 0xDB4775248B80FB57

# High bit of a block footer marks a hash index, which this reader does not parse.
NUM_RESTARTS_MASK = 0x7FFFFFFF

VALUE_TYPES = {
    0x0: "deletion",
    0x1: "value",
    0x2: "merge",
    0x7: "single-deletion",
    0xF: "range-deletion",
    0x11: "blob-index",
    0x17: "wide-column",
    0x18: "value-preferred",
}


def read_varint(buf, pos):
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated varint")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            raise ValueError("varint is too long")


def zigzag_decode(value):
    return (value >> 1) ^ -(value & 1)


def decompress_block(raw, compression_type):
    if compression_type == 0:
        return raw
    if compression_type == 1:
        return bytes(cramjam.snappy.decompress_raw(raw))
    if compression_type == 7:
        return bytes(cramjam.zstd.decompress(raw))
    if compression_type in (4, 5):
        # RocksDB prefixes LZ4 blocks with the uncompressed length.
        size, start = read_varint(raw, 0)
        return bytes(cramjam.lz4.decompress_block(raw[start:], size))
    raise ValueError(f"unsupported SST compression type {compression_type}")


def read_block(data, offset, size):
    if offset + size + BLOCK_TRAILER_SIZE > len(data):
        raise ValueError(
            f"block at offset {offset} size {size} runs past end of file"
        )
    raw = data[offset : offset + size]
    compression_type = data[offset + size]
    return decompress_block(raw, compression_type)


def block_entry_limit(block):
    if len(block) < 4:
        raise ValueError("block is shorter than its footer")
    footer = struct.unpack_from("<I", block, len(block) - 4)[0]
    if footer & ~NUM_RESTARTS_MASK:
        raise ValueError("data-block hash index is not supported")
    num_restarts = footer & NUM_RESTARTS_MASK
    trailer = (num_restarts + 1) * 4
    if trailer > len(block):
        raise ValueError("restart array is larger than the block")
    return len(block) - trailer


def iter_data_entries(block):
    """Yield (key, value) from a block that stores an explicit value length."""
    end = block_entry_limit(block)
    pos = 0
    previous = b""
    while pos < end:
        shared, pos = read_varint(block, pos)
        unshared, pos = read_varint(block, pos)
        value_len, pos = read_varint(block, pos)
        if shared > len(previous):
            raise ValueError("key prefix is longer than the previous key")
        fragment = block[pos : pos + unshared]
        pos += unshared
        value = block[pos : pos + value_len]
        pos += value_len
        if len(fragment) != unshared or len(value) != value_len:
            raise ValueError("entry runs past the end of the block")
        key = previous[:shared] + fragment
        previous = key
        yield key, value


def iter_index_handles(block):
    """Yield data-block (offset, size) from a format-version >= 4 index block.

    Index entries omit the value length. A restart entry stores a full block
    handle. A later entry that shares key bytes stores only a zigzag size delta.
    """
    end = block_entry_limit(block)
    pos = 0
    previous_key = b""
    previous_handle = None
    while pos < end:
        shared, pos = read_varint(block, pos)
        unshared, pos = read_varint(block, pos)
        fragment = block[pos : pos + unshared]
        pos += unshared
        if len(fragment) != unshared or shared > len(previous_key):
            raise ValueError("index entry key is truncated")
        previous_key = previous_key[:shared] + fragment
        if shared == 0 or previous_handle is None:
            offset, pos = read_varint(block, pos)
            size, pos = read_varint(block, pos)
        else:
            encoded_delta, pos = read_varint(block, pos)
            delta = zigzag_decode(encoded_delta)
            offset = previous_handle[0] + previous_handle[1] + BLOCK_TRAILER_SIZE
            size = previous_handle[1] + delta
        previous_handle = (offset, size)
        yield offset, size


def parse_footer(data):
    """Return (format_version, metaindex_handle, index_handle).

    index_handle is None for format version >= 6, where the index handle lives
    in the metaindex under the key b"rocksdb.index".
    """
    if len(data) < LEGACY_FOOTER_SIZE:
        raise ValueError("file is too small to be an SST")
    magic = struct.unpack_from("<Q", data, len(data) - 8)[0]
    if magic == LEGACY_BLOCK_BASED_MAGIC:
        footer = data[-LEGACY_FOOTER_SIZE:]
        pos = 0
        meta_off, pos = read_varint(footer, pos)
        meta_size, pos = read_varint(footer, pos)
        index_off, pos = read_varint(footer, pos)
        index_size, pos = read_varint(footer, pos)
        return 0, (meta_off, meta_size), (index_off, index_size)
    if magic != BLOCK_BASED_MAGIC:
        raise ValueError(f"not a block-based SST (magic {magic:#x})")
    if len(data) < NEW_FOOTER_SIZE:
        raise ValueError("file is too small for a versioned SST footer")
    version = struct.unpack_from("<I", data, len(data) - 12)[0]
    if version >= 6:
        footer = data[-NEW_FOOTER_SIZE:]
        # checksum type, extended magic, footer checksum, base checksum, then size
        metaindex_size = struct.unpack_from("<I", footer, 13)[0]
        footer_offset = len(data) - NEW_FOOTER_SIZE
        metaindex_end = footer_offset - BLOCK_TRAILER_SIZE
        metaindex_offset = metaindex_end - metaindex_size
        return version, (metaindex_offset, metaindex_size), None
    footer = data[-NEW_FOOTER_SIZE:]
    pos = 1  # skip checksum type
    meta_off, pos = read_varint(footer, pos)
    meta_size, pos = read_varint(footer, pos)
    index_off, pos = read_varint(footer, pos)
    index_size, pos = read_varint(footer, pos)
    return version, (meta_off, meta_size), (index_off, index_size)


def metaindex_handles(data):
    _version, metaindex, index_handle = parse_footer(data)
    handles = {}
    meta_block = read_block(data, *metaindex)
    for key, value in iter_data_entries(meta_block):
        pos = 0
        offset, pos = read_varint(value, pos)
        size, pos = read_varint(value, pos)
        handles[key] = (offset, size)
    if index_handle is not None:
        handles[b"rocksdb.index"] = index_handle
    if b"rocksdb.index" not in handles:
        raise ValueError("SST metaindex has no rocksdb.index entry")
    return handles


def iter_sst_records(path):
    """Yield (user_key, sequence, value_type, value) for every data-block entry."""
    with open(path, "rb") as handle:
        data = handle.read()
    handles = metaindex_handles(data)
    index_block = read_block(data, *handles[b"rocksdb.index"])
    for offset, size in iter_index_handles(index_block):
        data_block = read_block(data, offset, size)
        for internal_key, value in iter_data_entries(data_block):
            if len(internal_key) < 8:
                raise ValueError("internal key is shorter than its sequence footer")
            user_key = internal_key[:-8]
            packed = int.from_bytes(internal_key[-8:], "little")
            yield user_key, packed >> 8, packed & 0xFF, value


def display_bytes(raw):
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.hex()
    if text.isprintable():
        return text
    return raw.hex()


def format_record(user_key, sequence, value_type, value):
    type_name = VALUE_TYPES.get(value_type, f"type {value_type}")
    line = f"    {display_bytes(user_key)}  seq {sequence}  {type_name}"
    if value:
        line += f"  {display_bytes(value)}"
    return line


def sst_filesystem_path(db_path, name):
    # RocksDB reports live files as "/000012.sst" relative to the DB directory.
    # os.path.join would treat that leading slash as an absolute path.
    if name.startswith("/"):
        return db_path.rstrip("/") + name
    return os.path.join(db_path, name)


def level_count(db):
    count = 0
    while db.property_int_value(f"rocksdb.num-files-at-level{count}") is not None:
        count += 1
        if count > 64:
            break
    return count


def print_database(db_path):
    db = Rdict(db_path, access_type=AccessType.read_only())
    try:
        active = db.property_int_value("rocksdb.num-entries-active-mem-table") or 0
        immutable = db.property_int_value("rocksdb.num-entries-imm-mem-tables") or 0
        files = db.live_files()
        levels = level_count(db)
    finally:
        db.close()

    print(db_path)
    print()
    if active or immutable:
        print(f"memtable: {active} entries not yet flushed")
        if immutable:
            print(f"immutable memtables: {immutable} entries waiting to flush")
        print("Those entries are not in a level until a flush.")
    else:
        print("memtable: empty")
    print()

    by_level = {}
    highest = levels - 1
    for meta in files:
        by_level.setdefault(meta["level"], []).append(meta)
        highest = max(highest, meta["level"])

    for level in range(highest + 1):
        level_files = by_level.get(level, [])
        if not level_files:
            print(f"L{level}  empty")
            continue
        total_bytes = sum(meta["size"] for meta in level_files)
        total_entries = sum(meta["num_entries"] for meta in level_files)
        noun = "file" if len(level_files) == 1 else "files"
        print(
            f"L{level}  {len(level_files)} {noun}, "
            f"{total_bytes} bytes, {total_entries} entries"
        )
        if level == 0 and len(level_files) > 1:
            print("  newest file first")
        for meta in level_files:
            filename = os.path.basename(meta["name"])
            deletions = meta.get("num_deletions") or 0
            deletion_note = f", {deletions} deletions" if deletions else ""
            print(
                f"  {filename}  {meta['size']} bytes, "
                f"{meta['num_entries']} entries{deletion_note}"
            )
            path = sst_filesystem_path(db_path, meta["name"])
            try:
                for record in iter_sst_records(path):
                    print(format_record(*record))
            except (OSError, ValueError, cramjam.DecompressionError) as error:
                start = display_bytes(meta.get("start_key") or b"")
                end = display_bytes(meta.get("end_key") or b"")
                print(f"    could not read keys ({error})")
                print(f"    key range {start} .. {end}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Print RocksDB LSM levels and the keys stored in each."
    )
    parser.add_argument("db_path", help="path to a RocksDB directory")
    args = parser.parse_args()
    db_path = os.path.abspath(args.db_path)
    if not os.path.isdir(db_path):
        sys.exit(f"not a database directory: {db_path}")
    try:
        print_database(db_path)
    except RuntimeError as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
