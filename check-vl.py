#!/usr/bin/env python

import argparse
import json
import logging
import os
from string import Template
import subprocess
import tempfile
import time
import urllib2


DOCKER_IMAGE = "bwilsonripple/rippled:latest"

def run_command(args):
    logging.debug(" ".join(args))
    return subprocess.check_output(args)

def get_validators(siteUri, publisherKey):
    with tempfile.NamedTemporaryFile(delete=False) as tmpValTxt:
        s = Template('[validator_list_sites]\n$site_uri\n[validator_list_keys]\n$list_key')
        tmpValTxt.write(s.substitute(site_uri=siteUri, list_key=publisherKey))

    run_command(["docker", "run", "-d", "--rm", "-v",
        "{0}:/opt/ripple/etc/validators.txt".format(tmpValTxt.name),
        "--net=host", "--name", "myrippled", DOCKER_IMAGE])
    time.sleep(3)

    status = run_command(["docker", "exec", "myrippled",
        "/opt/ripple/bin/rippled", "-q", "validator_list_sites"])
    validators = run_command(["docker", "exec", "myrippled",
        "/opt/ripple/bin/rippled", "-q", "validators"])

    logging.debug(status)
    logging.debug(validators)

    run_command(["docker", "stop", "myrippled"])

    os.unlink(tmpValTxt.name)

    ret = json.loads(validators)["result"]

    ret["status"] = json.loads(status)["result"]["validator_sites"][0]["last_refresh_status"]

    return ret

def serve_vl(vl_file):
    run_command(["docker", "run", "-p", "8000:8000", "-d", "--rm", "-v",
        "{0}:/opt/vlserver/validators".format(os.path.abspath(vl_file)), "-w",
        "/opt/vlserver", "--entrypoint", "python", "--name", "myserver",
        DOCKER_IMAGE, "-m", "SimpleHTTPServer"])

def stop_server():
    run_command(["docker", "stop", "myserver"])

def main(args):
    print "Comparing {0} with existing list at {1}\n".format(
        args.vl_file, args.vl_site)

    req = urllib2.Request(args.vl_site, headers={'User-Agent': "Custom User-Agent"})
    contents = urllib2.urlopen(req).read()
    site_unl = json.loads(contents)

    with open(args.vl_file, 'r') as json_data:
        unl = json.load(json_data)

        oldValidators = get_validators(args.vl_site, site_unl['public_key'])

        serve_vl(args.vl_file)

        newValidators = get_validators("http://127.0.0.1:8000/validators", unl['public_key'])

        stop_server()

        print "validator list was " + newValidators["status"] + "\n"

        oldList = oldValidators["publisher_lists"][0]
        newList = newValidators["publisher_lists"][0]

        diff = []
        newVals = newList["list"]
        for val in oldList["list"]:
            if val in newVals:
                print " " + val
                newVals.remove(val)
            else:
                print "-" + val

        for val in newVals:
            print "+" + val

        if newValidators["status"] == "accepted":
            print "\nExpiration: {0} -> {1}".format(oldList["expiration"], newList["expiration"])
            print "\nSequence: {0} -> {1}".format(oldList["seq"], newList["seq"])

parser = argparse.ArgumentParser(
    description="Compare XRP Ledger validator lists")

parser.add_argument("-v", "--verbose", help="verbose logging",
    action="store_true")
parser.add_argument("--vl_site",
    help="URI of existing published validator list (default: https://vl.ripple.com)",
    default="https://vl.ripple.com")

requiredNamed = parser.add_argument_group("required arguments")
requiredNamed.add_argument("--vl_file",
    help="path to file containing signed validator list", required=True)

args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    main(args)
