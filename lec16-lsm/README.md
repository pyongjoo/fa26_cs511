```
./init_db.sh ./my-db
./put.sh ./my-db a 1 b 2 c 3
./put.sh ./my-db hello "world wide" d 4
./show_lsm.py ./my-db
./compact.sh ./my-db
./show_lsm.py ./my-db
```
