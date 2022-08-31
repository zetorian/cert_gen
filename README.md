# HUGE WIP

Anyway, this is a mimimal working copy of my simple automation to generate certs for use with etcd by leveraging cfssl.

It takes a few shortcuts, and a couple dirty hacks, but it does _work_ so there's that.

## Usage:

```
# Edit config.yaml to your liking
mkdir <output_dir>
./cert_gen.py config.yaml <output_dir>
```