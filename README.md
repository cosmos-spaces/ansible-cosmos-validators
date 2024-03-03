# Cosmos CometBFT Setup with Horcrux Support

This repository secures cloud provider servers, installs and configures CometBFT based chains for both, validator and sentry (relayer) nodes, and installs Horcrux using [Ansible]("https://docs.ansible.com/ansible/latest/getting_started/index.html).

## Design Philosophy
1. Secure server setup
1. Extendable to most CometBFT-based (Formerly known as Tendermint) chains
1. Support both mainnet and testnet
1. Support horcrux install and node config updates
1. Stable playbooks and roles; Customizable variables
1. Support essential functions (snapshot, state-sync, public RPC/API endpoints) through separate playbooks

## TL/DR
Run the desired playbook with the following arguments:

```bash
# Node Setup
ansible-playbook setup.yml -e "target=<mainnet|testnet|horcrux_cluster>" -e "ssh_port=<non_standard_ssh_port>"

# Install/Configure Chain
ansible-playbook main.yml -e "target=<mainnet|testnet>" -e "network=<chain>"

# Install/Configure Horcrux
ansible-playbook horcrux.yml
```

## Architecture
For every network where we run a validator on mainnet, we run 2 sentry (relayer) nodes connected to a 3/3 cosigner node horcrux cluster. 

Leveraging [Horcrux](https://github.com/strangelove-ventures/horcrux/tree/main) provides high-availability while maintaining high security and avoiding double signing via consensus and failover detection mechanisms. This allows to connect multiple sentry (relayer) nodes to cosigner nodes, which reduces downtime and block signing failures, and increases fault tolerance and resiliency of blockchain operations.

## Node Setup
Typically, a cloud server provides a machine with root access and insecure setup. This ansible playbook is designed to address those issues. It is based on Ubuntu 22.04, but it should be applicable to other Ubuntu images. To run this playbook, you will need a user with sudo privileges. This playbook does not create a user on purpose as a security measure to avoid using root. This playbook will perform the following:

1. Set the hostname (based on inventory file)
1. Update server: Simply update and upgrade all applications shipped with the OS.
1. Install and configure essential software dependencies
1. Install ufw
1. Install firewall
1. Install fail2ban
1. Install cosmovisor
1. Optionally install node exporter (configurable in inventory)
1. Optionally install promtail (configurable in inventory)
1. Optionally install nginx (configurable in inventory)

### Secure Node

1. Disable the default ssh port of 22 and set up the alternative port.
1. Deny all incoming traffic.
1. Enable firewall to allow the ssh alternative port from the bastion/jumpbox ip.
1. Disable root account access.
1. Disable password authentication.

### Variables
Look at the `inventory.sample.yml` file. You will see an example of how the structure should be to configure your CometBFT clusters:

1. `target`: Required. Whether `mainnet` or `tesnet`.
1. `ansible_host`: Required. The IP address of the server(s).
1. `ssh_port`: Required. Alternate ssh port to configure on the server. This can be different per host. By default, it will apply the same port for all servers.
1. `server_hostname` Required. Sets the hostname to this value.
1. `bastion_ip` Required. Bastion/Jumpbox IP to allow ssh access to the server. It can be an address range as well.

### Run node setup playbook
```bash
# Node Setup
ansible-playbook setup.yml -e "target=<mainnet|testnet|horcrux_cluster>" -e "ssh_port=<non_standard_ssh_port>"
```

## Install/Configure Chain

As mentioned above, we run 2 sentry (relayer) nodes connected to a 3/3 cosigner node horcrux cluster. However, this repo supports configuring chain nodes as a `Validator` or as a `Relayer`, each with different settings described below. If you do not wish to use Horcrux, set the type to `Validator` for each corresponding node.

### Opinionated Configuration

We have 2 strong opinions about the node configuration:

1. Each network will have its custom 3-digit port prefix. This is to prevent port collision if you run multiple nodes on the same server. For example, you can configure Babylon with the custom port prefix 109 and Osmosis with 110. It is up to you what port prefix to use.
1. Each type of node will have its setting based on our experience. For example, the main node (Validator) has null indexer, and 100/0/<prime number> pruning, and Sentry node has kv indexer and 1000/100/<prime number> pruning. We will force these settings on you unless you fork the code.

### Variables

Look at the `inventory.sample.yml` file. You will see an example of how the structure should be to configure your CometBFT clusters. All these values can be set per mainnet/testnet, host, network or global.

1. `target`: Required. Whether mainnet or tesnet.
1. `ansible_host`: Required. The IP address of the server.
1. `network`: Required. The chain network name to install/configure (should match file under group_vars/<testnet/mainnet>).
1. `type`: Required. It can be `validator` or `relayer`. Each is opinionated in its configuration settings.
1. `ansible_user`: The sample file assumes `ubuntu`, but feel free to use another username. This user needs sudo privilege.
1. `ansible_port`: The sample file assumes `22`. If you ran the node setup playbook, it should match ssh_port.
1. `ansible_ssh_private_key_file`: path to ssh key file.
1. `var_file`: It tells the program where to look for the variable file.
1. `user_dir`: The user's home directory. In the sample inventory file this is a computed variable based on the ansible_user. It assumes that it is not a root user and its home directory is `/home/{{ansible_user}}`.
1. `path`: This is to make sure that the ansible_user can access the `go` executable.
1. `node_name`: This is your node name or moniker for the config.toml file.

There are additional variables under `group_vars/all.yml` for global configuration applied to all networks (chains).

1. `node_exporter_version`: Node exporter version to install.
1. `promtail_version`: Promtail version to install.
1. `go_version`: Go version to install.
1. `cosmovisor_version`: Cosmovisor version to install.
1. `cosmovisor_service_name`: Systemctl prefix for the chain's (network) cosmovisor service.
1. `node_exporter`: Default is `true`. Change it to `false` if you do not want to install node_exporter. If true, enables the prometheus port in config.toml.
1. `promtail`: Default is `false`. Change it to `true` if you want to install promtail.
1. `nginx`: Default is `false`. Change it to `true` if you want to install nginx.
1. `log_monitor`: Enter your monitor server IP if you install promtail.
1. `log_name`: This is the server's name for the promtail service.
1. `pagerduty_key`: This is the PagerDuty key if you use TenderDuty.
1. `enableapi` Default is `false`. Set to `true` if you want to enable the api endpoint. 
1. `enablegrpc`: Default is `false`. Set to `true` if you want to enable the grpc endpoint.
1. `publicrpc`: Default is `false`. Set to `true` if you want to allow the rpc port on the server.
1. `external_address`: IP address to set as an external address in config.toml.

Look at `group_var/mainnet|testnet/<network>.yaml` for network (chain) specific variables.

### Run install/configure playbook
```bash
# Install/Configure Chain
ansible-playbook main.yml -e "target=<mainnet|testnet>" -e "network=<chain>"
```

## Install/Configure Horcrux
This playbook will install Horcrux, a multi-party-computation (MPC) signing service for CometBFT, on the servers defined in inventory.yml under `horcrux_cluster`. 

### Variables

1. `ansible_host`: Required. The IP address of the server.
1. `type`: Should always be set to horcrux.
1. `restart_horcrux`: Defaults to `true`. Change to `false` if you do not want the horcrux service to restart after a config update.
1. `nodes`: priv-val interface listen address for the chain sentry nodes to add to the config.

There are additional variables under `group_vars/all.yml` for global configuration applied to all horcrux cosigner nodes.

1. `horcrux_repo`: Repo URL where the horcrux code resides.
1. `horcrux_version`: Horcrux version to install.
1. `horcrux_cosigner_port`: Defaults to `2222`. Port cosigner nodes listen on.

### Run install/configure playbook
```bash
# Install/Configure Horcrux
ansible-playbook horcrux.yml
```

### Manual Steps
- Horcrux uses secp256k1 keys to encrypt (ECIES) and sign (ECDSA) cosigner-to-cosigner p2p communication. This is done by encrypting the payloads that are sent over GRPC between cosigners. Due to security reasons, this step must be done manually, and the key files should be copied to each cosigner accordingly after running the following command:
```bash
horcrux create-ecies-shards --shards 3
```
- Horcrux uses threshold Ed25519 cryptography to sign a block payload on the cosigners and combine the resulting signatures to produce a signature that can be validated against your validator's Ed25519 public key. On your local machine which contains your full `priv_validator_key.json` key file(s), run the following command and copy the files to each cosigner accordingly:
```bash
horcrux create-ed25519-shards --chain-id <chain> --key-file /path/to/priv_validator_key.json --threshold 2 --shards 3
```
- To avoid double-signing issues, manually supply signer state data to each cosigner.

For more information, refer to the [documentation](https://github.com/strangelove-ventures/horcrux/blob/main/docs/migrating.md).


## Playbooks

| Playbook                       | Description                                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------------------ |
| `main.yml`                     | The main playbook to set up a node                                                               |
| `setup.yml`                    | Secure the server with ssh config changes and firewall rules, and install dependencies           |
| `support_backup_node.yml`      | Install snapshot, state_sync, resync, genesis and prune script on backup node                    |
| `support_snapshot.yml`         | Install snapshot script and a cron job                                                           |
| `support_state_sync.yml`       | Install state-sync script                                                                        |
| `support_resync.yml`           | Install weekly scheduled state-sync and recovery script                                          |
| `support_genesis.yml`          | Install a script to upload genesis                                                               |
| `support_prune.yml`            | Install a script to prune using cosmprund                                                        |
| `support_public_endpoints.yml` | Set up Nginx reverse proxy for public PRC/ API                                                   |
| `support_seed.yml`             | Install seed node with Tenderseed. You need a node_key.json.j2 file so the node_id is consistent |
| `support_tenderduty.yml`       | Install Tenderduty                                                                               |
| `support_price_feeder.yml`     | Install price feeders for selected networks (such Umee, Kujira, etc.)                             |
| `support_scripts.yml`          | Install scripts to make node operations easier                                                   |
| `support_sync_snapshot.yml`    | Sync node from a snapshot                                                                        |
| `support_remove_node.yml`      | Remove a node and clean up                                                                       |
| `support_update_min_gas.yml`   | Update minimum gas price                                                                         |
| `horcrux.yml`                  | Install horcrux cluster                                                                          |
| `support_horcrux_config.yml`   | Add additional nodes to the horcrux config                                                       |

### Selected playbook Usage Example

##### support_seed

```bash
ansible-playbook support_seed.yml -e "target=<mainnet|testnet>" -e "network=<chain>" -e "seed=190c4496f3b46d339306182fe6a507d5487eacb5@65.108.131.174:36656"
```

##### support_tenderduty

```bash
ansible-playbook support_tenderduty.yml -e "target=<mainnet|testnet>" -e "network=<chain>" -e "key=junovalcons1qyw2x2sjp40cqasdfyuiahsdfknasdkneafs"
```

##### support_scripts

```bash
ansible-playbook support_scripts.yml -e "target=<mainnet|testnet>"
```

Currently, we have 4 supported scripts. Their usage is documented below using Juno as example:

```bash
./scripts/bank_balances/juno.sh
./scripts/bank_send/juno.sh ADDRESS 1000000ujuno
./scripts/distribution_withdrawal/juno.sh
./scripts/gov_vote/juno.sh 1 yes
```

##### support_horcrux_config

```bash
ansible-playbook support_horcrux_config.yml
```

## Contribute

We believe we can always improve so feel free to fork this repo and create a PR with your changes so other people can also benefit from them.

## Acknowledgement

This could not have been possible without the help of the people listed below. **Thank you very much for providing this framework and creating an environment of collaboration while promoting automation, reliability, and security:**

- [Polkachu]("https://polkachu.com/")
- [Strangelove Labs Inc.]("https://strange.love/)

## Known Issues

Because this repo tries to accommodate as many Tendermint-based chains as possible, it cannot adapt to all edge cases. Here are some known issues and how to resolve them.

| Chain            | Issue                                                    | Solution                                                                             |
| ---------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Axelar           | Some extra lines at the end of app.toml                  | Delete extra lines and adjust some settings these extra lines are supposed to change |
| Canto            | genesis file needs to be unwrapped from .result.genesis  | Unwrap genesis with jq command                                                       |
| Injective        | Some extra lines at the end of app.toml                  | Delete extra lines and adjust some settings these extra lines are supposed to change |
| Kichain          | Some extra lines at the end of app.toml                  | Delete extra lines and adjust some settings these extra lines are supposed to change |
| Celestia testnet | inconsistent config.toml file variable naming convention | Manually adjust config.toml file                                                     |