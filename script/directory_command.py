import subprocess
import yaml
import os

# The purpose of this file and directory.yaml is to run chain wide operations rather than server specific operations

# Required. Accepts string input without the .yml. Example input would be: "upgrade"
playbook_input = input("Please enter the playbook which you would like to run as a directory command: ")
if not os.path.exists(f"{playbook_input}.yml"):
    print(f"Error: Playbook '{playbook_input}.yml' not found.")
    exit(1)

# Required. Accepts string input of filenames found in vars without the .yml. Example input would be: "babylon"
chain_input = input("Please enter the chains to take action on: ")

# Required. Accepts string input of filenames found in vars. Example input would be: "mainnet"
network_input = input(f"Please enter the network of the {chain_input} to take action on: ")
if network_input not in ['mainnet','testnet']:
    print(f"Error: network_input '{network_input}' not mainnet or testnet.")
    exit(1)
if not os.path.exists(f"vars/{network_input}/{chain_input}.yml"):
    print(f"Error: chain '{chain_input}' not found.")
    exit(1)

# Optional. Accepts additional arguments to be passed to the playbook. Example input would be: "-e test=4 -e temp=5"
# This is where you would put: -e var_file=vars/<network>/<chain>.yml
extra_args_input = input("Please enter variables as a full string: ")

# try and catch in case missing directory.yaml
try:
    # Read in current directory yaml
    with open("directory.yaml",'r') as file:
        # Grabbing file data
        directory_data = yaml.safe_load(file)
        # Getting only want information
        data = directory_data['chains'][chain_input][network_input]
        # Check with user that the information is right against the host list
        print(f"Do you want to proceed on the following? action = {playbook_input}, chain = {chain_input}, network = {network_input}, Hosts to run against: {data}")
        proceed = input("Please enter y/n! ")
        if proceed.lower() == 'y':
            # looping through hosts
            for host in data:
                print(f"Running command against {host}")
                cmd = [
                    "ansible-playbook",
                    f"{playbook_input}.yml",
                    "-e", f"target={host}",
                    "-e", f"chain={chain_input}",
                    "-e", f"network={network_input}",
                    *extra_args_input.split()
                    ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                print("Return Code:", result.returncode)
                print("\n\n\n\n")
except Exception as e:
    print(f"Error reading YAML file: {e}")
    exit(1)