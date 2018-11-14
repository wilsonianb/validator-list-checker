# validator-list-checker

Checks signed XRP Ledger validator list against existing published list.

Runs rippled in a Docker container, first using the existing published list then using the provided list.

## Dependencies

- [docker](https://docs.docker.com/install/)

## Run

Save the signed validator list to a local file and run:

```
sudo ./check-vl.py --vl_file /path/to/your/vl/file --vl_site https://vl.ripple.com
```
