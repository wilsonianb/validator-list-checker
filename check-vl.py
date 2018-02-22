#!/usr/bin/env python

import argparse
import json
import logging
import os
import subprocess
import threading
import time

PORT = 8000

PUBLISHER_KEYS = {
  "ED2677ABFFD1B33AC6FBC3062B71F1E8397C1505E1C42C64D11AD1B28FF73F4734": {
    "name": "production",
    "site": "https://vl.ripple.com"
  },
  "ED264807102805220DA0F312E71FC2C69E1552C9C5790F6C25E3729DEB573D5860": {
    "name": "altnet",
    "site": "https://vl.altnet.rippletest.net"
  }
}

DOCKER_IMAGE = "bwilsonripple/rippled:latest"

def run_command(args):
    logging.debug(" ".join(args))
    return subprocess.check_output(args)

def get_validators(valTxt):
    run_command(["docker", "run", "-d", "--rm", "-v",
        "{0}/{1}:/opt/ripple/etc/validators.txt".format(os.getcwd(), valTxt),
        "--net=host", "--name", "myrippled", DOCKER_IMAGE])
    time.sleep(3)

    status = run_command(["docker", "exec", "myrippled",
        "/opt/ripple/bin/rippled", "-q", "validator_list_sites"])
    validators = run_command(["docker", "exec", "myrippled",
        "/opt/ripple/bin/rippled", "-q", "validators"])

    logging.debug(status)
    logging.debug(validators)

    run_command(["docker", "stop", "myrippled"])

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
    with open(args.vl_file, 'r') as json_data:
        unl = json.load(json_data)

        if unl["public_key"] not in PUBLISHER_KEYS:
            logging.error("Unrecognized publisher public key")
            return

        print "Comparing {0} with existing {1} list at {2}\n".format(
            args.vl_file, PUBLISHER_KEYS[unl["public_key"]]["name"],
            PUBLISHER_KEYS[unl["public_key"]]["site"])

        oldValidators = get_validators(
            PUBLISHER_KEYS[unl["public_key"]]["name"] + "/validators.txt")

        serve_vl(args.vl_file)

        newValidators = get_validators(
            PUBLISHER_KEYS[unl["public_key"]]["name"] + "/local-validators.txt")

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

requiredNamed = parser.add_argument_group("required named arguments")
requiredNamed.add_argument("--vl_file",
    help="path to file containing signed validator list", required=True)

args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    main(args)
