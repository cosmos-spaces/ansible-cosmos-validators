import subprocess
import yaml
import os

# The purpose of this file and directory.yaml is to run chain wide operations rather than server specific operations

# Required. Accepts string input without the .yml. Example input would be: "upgrade"
playbook_input = input("Please enter the playbook which you would like to run as a directory command: ")
if not os.path.exists(f"{playbook_input}.yml"):
    print(f"Error: Playbook '{playbook_input}.yml' not found.")

# Required. Accepts string input of filenames found in vars without the .yml. Example input would be: "babylon"
chain_input = input("Please enter the chains to take action on: ")

# Required. Accepts string input of filenames found in vars. Example input would be: "mainnet"
network_input = input(f"Please enter the network of the {chain_input} to take action on: ")
if network_input not in ['mainnet','testnet']:
    print(f"Error: network_input '{network_input}' not mainnet or testnet.")
if not os.path.exists(f"vars/{network_input}/{chain_input}.yml"):
    print(f"Error: chain '{chain_input}' not found.")

# TODO
# Optional. Accepts additional arguments to be passed to the playbook. Example input would be: "test=4,temp=5"
# extra_args_input = input("Please enter variables as a csv: ")

try:
    # Read in current directory yaml
    with open("directory.yaml",'r') as file:
        # grabbing data
        directory_data = yaml.safe_load(file)
        # TODO add more comments explaining
        data = directory_data['chains'][chain_input][network_input]
        for host in data:
            print(f"Running command against {host}")
            cmd = [
                "ansible-playbook",
                f"{playbook_input}.yml",
                "-e", f"target={host}",
                "-e", f"chain={chain_input}.yml"
                ]
            print(cmd)
            result = subprocess.run(cmd, capture_output=True, text=True)
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            print("Return Code:", result.returncode)
except Exception as e:
    print(f"Error reading YAML file: {e}")
    exit(1)