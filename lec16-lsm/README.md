```
./init_db.sh /tmp/lsm-demo
./put.sh /tmp/lsm-demo a 1
./put.sh /tmp/lsm-demo b 2
./put.sh /tmp/lsm-demo hello "world wide"
.venv/bin/python3 show_lsm.py /tmp/lsm-demo
```