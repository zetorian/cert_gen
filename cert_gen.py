#!/usr/bin/env python

import yaml
# Calling yaml.load without specifying `Loader=` is depricated, might as well use the quick one
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import json
import subprocess
import sys
import os

class Config:
    expiry = "24h"
    key_algo = "rsa"
    key_size = "4096"
    details = {"OU": "example.com"}
    include_localhost = False
    cluster_name = "etcd.example.com"
    nodes = {"1.example.com": ["1.1.1.1", "1.2.3.4"],
             "2.example.com": ["2.1.1.1", "2.2.3.4"]}

    # Parse the yaml input into a more structured object.
    # I'm gonna have to make a shitload of nested dicts here anyway
    # Might as well do one less while I can
    def __init__(self, raw_etcd):
        self.expiry = raw_etcd.get("expiry", self.expiry)
        self.details = raw_etcd.get("details", self.details)
        self.include_localhost = raw_etcd.get("include_localhost", self.include_localhost)

        if "key" in raw_etcd:
            self.key_algo = raw_etcd["key"].get("algo", self.key_algo)
            self.key_size = raw_etcd["key"].get("size", self.key_size)

        if "cluster" in raw_etcd: 
            # Transpose the dict as a list, to get an indexable .keys() object
            cluster_tmp = list(raw_etcd["cluster"])

            if len(cluster_tmp) > 1:
                print("ERROR: only one cluster is supported per etcd block")
                exit(1)

            self.cluster_name = cluster_tmp[0]

            self.nodes = raw_etcd["cluster"].get(self.cluster_name, self.nodes)
            

def usage():
    print(("USAGE: %s config.yaml <output_dir: cwd>" % sys.argv[0]))
    exit(0)

def load_conf(conf_fn):
    raw_conf = yaml.load(open(conf_fn), Loader=Loader)
    return Config(raw_conf["etcd"])

# Why not just generate the json directly.
# Because fuck you, that's why
def gen_ca_conf(conf):
    ca_conf = {
                "signing": {
                    "default": { "expiry": conf.expiry },
                    "profiles": {
                        "server": {
                            "expiry": conf.expiry,
                            "usages": [ "signing", "key encipherment", "server auth" ]
                        },
                        "client": {
                            "expiry": conf.expiry,
                            "usages": [ "signing", "key encipherment", "client auth" ]
                        },
                        "peer": {
                            "expiry": conf.expiry,
                            "usages": [ "signing", "key encipherment", "server auth", "client auth" ]
                        }
                    }
                }
            }

    return json.dumps(ca_conf)

def gen_ca_csr(conf):
    ca_csr = {
                "CN": conf.cluster_name,
                "key": {
                    "algo": conf.key_algo,
                    "size": conf.key_size
                },
                "names": [ conf.details ]
            }
    return json.dumps(ca_csr)

def gen_peer_csrs(conf):
    csrs = dict()
    for peer, ips in conf.nodes.items():
        peer_csr = {
                        "CN": peer,
                        "hosts": [
                            peer,
                            *ips # flatten the list into it's elements
                        ],
                        "key": {
                            "algo": conf.key_algo,
                            "size": conf.key_size
                        },
                        "names": [ conf.details ]
                    }
        csrs[peer] = json.dumps(peer_csr)

    return csrs

def main():
    if len(sys.argv) < 2:
        print("ERROR: config file is required")
        usage()
    else:
        conf = load_conf(sys.argv[1])

    # I should probably do some validation on this, it could get ugly
    if len(sys.argv) > 2:
        out_dir = sys.argv[2]
        os.chdir(out_dir)
        if not os.path.isdir("json"):
            os.mkdir("json")

    config_prefix = "json/" # Reusable config prefix, this should probably be a cli arg :shrug:

    ca_conf_json = gen_ca_conf(conf)
    ca_conf_f = config_prefix + "ca_conf.json"
    with open(ca_conf_f, "wt") as ca_conf:
        ca_conf.write(ca_conf_json)
    #print(ca_conf_json)

    ca_csr_json = gen_ca_csr(conf)
    ca_csr_f = config_prefix + "ca_csr.json"
    with open(ca_csr_f, "wt") as ca_csr:
        ca_csr.write(ca_csr_json)
    #print(ca_csr_json)

    peer_csrs = gen_peer_csrs(conf)
    for peer_name, peer_csr_json in peer_csrs.items():
        peer_csr_f = config_prefix + peer_name + ".csr.json"
        with open(peer_csr_f, "wt") as peer_csr:
            peer_csr.write(peer_csr_json)

        if not os.path.isdir(peer_name):
            os.mkdir(peer_name)
        #print(peer_csr_json)

    # Ensure that we have a ca folder for the output
    if not os.path.isdir("ca"):
        os.mkdir("ca")

    # I hope to later manage this internally to python, and probably pipe and parse the json mysel
    # For now, some shitty subshell fuckery will do just fine.
    subprocess.run("cfssl gencert -initca %s | (cd ca; cfssljson -bare ca -)" % (ca_csr_f), shell=True)

    for peer_name in peer_csrs.keys():
        subprocess.run("cfssl gencert -ca=ca/ca.pem -ca-key=ca/ca-key.pem -config=%s -profile=peer %s\
                        | (cd %s; cfssljson -bare %s)" % (ca_conf_f,
                                                          config_prefix + peer_name + ".csr.json",
                                                          peer_name,
                                                          peer_name
                                                          ), shell=True)

    


    

    
    
        

if __name__ == "__main__":
    main()
