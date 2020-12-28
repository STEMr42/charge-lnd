#!/usr/bin/env python3
import sys
from policy import Policy
import fmt

def debug(message):
    sys.stderr.write(message + "\n")

class Matcher:
    def __init__(self, lnd, config):
        self.lnd = lnd
        self.config = config
        self.default = None
        self.policies = []

        sections = config.sections()
        for s in sections:
            if s == 'default':
                self.default = config[s]
            else:
                self.policies.append(s)

    def get_policy(self, channel):
        # iterate policies, find first match based on matchers. If no match, use default
        for policy in self.policies:
            policy_conf = self.config[policy]
            if self.eval_matchers(channel, policy_conf):
                return Policy(self.lnd, policy, policy_conf)

        return Policy(self.lnd, 'default', self.default);

    def eval_matchers(self, channel, policy_conf):
        map = {
            'chan'  : self.match_by_chan,
            'node'  : self.match_by_node
        }
        namespaces = []
        for key in policy_conf.keys():
            keyns = key.split(".")
            if len(keyns) > 1:
                namespaces.append(keyns[0])

        matches_policy = True
        for ns in namespaces:
            if not ns in map:
                debug("Unknown namespace '%s'" % ns)
                sys.exit(1)
            matches_policy = matches_policy and map[ns](channel, policy_conf)
        return matches_policy

    def match_by_node(self, channel, config):
        accepted = ['id','min_channels','max_channels','min_sats','max_sats']
        for key in config.keys():
            if key.split(".")[0] == 'node' and key.split(".")[1] not in accepted:
                debug("Unknown property '%s'" % key)
                sys.exit(1)

        if 'node.id' in config and not channel.remote_pubkey in config.getlist('node.id'):
            return False

        node_info = self.lnd.get_node_info(channel.remote_pubkey)

        if 'node.min_channels' in config and not config.getint('node.min_channels') <= node_info.num_channels:
            return False
        if 'node.max_channels' in config and not config.getint('node.max_channels') >= node_info.num_channels:
            return False
        if 'node.min_sats' in config and not config.getint('node.min_sats') <= node_info.total_capacity:
            return False
        if 'node.max_sats' in config and not config.getint('node.max_sats') >= node_info.total_capacity:
            return False

        return True

    def match_by_chan(self, channel, config):
        accepted = ['id','initiator','private','max_ratio','min_ratio','max_capacity','min_capacity','min_base_fee_msat','max_base_fee_msat','min_fee_ppm','max_fee_ppm']
        for key in config.keys():
            if key.split(".")[0] == 'chan' and key.split(".")[1] not in accepted:
                debug("Unknown property '%s'" % key)
                sys.exit(1)

        if 'chan.id' in config and not channel.chan_id in [fmt.parse_channel_id(x) for x in config.getlist('chan.id')]:
            return False
        if 'chan.initiator' in config and not channel.initiator == config.getboolean('chan.initiator'):
            return False
        if 'chan.private' in config and not channel.private == config.getboolean('chan.private'):
            return False

        ratio = channel.local_balance/(channel.local_balance + channel.remote_balance)
        if 'chan.max_ratio' in config and not config.getfloat('chan.max_ratio') >= ratio:
            return False
        if 'chan.min_ratio' in config and not config.getfloat('chan.min_ratio') <= ratio:
            return False
        if 'chan.max_capacity' in config and not config.getint('chan.max_capacity') >= channel.capacity:
            return False
        if 'chan.min_capacity' in config and not config.getint('chan.min_capacity') <= channel.capacity:
            return False

        chan_info = self.lnd.get_chan_info(channel.chan_id)
        if not chan_info:
            return False
        my_pubkey = self.lnd.get_own_pubkey()
        peernode_policy = chan_info.node1_policy if chan_info.node2_pub == my_pubkey else chan_info.node2_policy

        if 'chan.min_base_fee_msat' in config and not config.getint('chan.min_base_fee_msat') <= peernode_policy.fee_base_msat:
            return False
        if 'chan.max_base_fee_msat' in config and not config.getint('chan.max_base_fee_msat') >= peernode_policy.fee_base_msat:
            return False
        if 'chan.min_fee_ppm' in config and not config.getint('chan.min_fee_ppm') <= peernode_policy.fee_rate_milli_msat:
            return False
        if 'chan.max_fee_ppm' in config and not config.getint('chan.max_fee_ppm') >= peernode_policy.fee_rate_milli_msat:
            return False

        return True
