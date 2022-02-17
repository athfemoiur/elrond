import logging
from pprint import pprint

import requests
from erdpy.accounts import Address, Account
from erdpy.proxy import ElrondProxy
from erdpy.transactions import Transaction
from erdpy.wallet import generate_pair

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ElrondHandler:
    base_url = 'https://gateway.elrond.com/'

    urls = dict(
        shard_block='block/{shard_number}/by-nonce/{block_height}/?withTxs=true',
        block='hyperblock/by-nonce/{block_height}'
    )

    def __init__(self):
        self.elrond_proxy = ElrondProxy('https://gateway.elrond.com')

    @classmethod
    def make_request(cls, url, method, **kwargs):
        url = cls.base_url + url
        logger.debug(f"[making request]-[method: {method}]-[URL: {url}]-[kwargs: {kwargs}]")

        try:
            req = requests.request(method, url, **kwargs)
            req.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.warning(
                f'[making request failed]-[response err: {e.response.text}]-[status code: {e.response.status_code}]'
                f'-[URL: {url}]-[exc: {e}]'
            )
            raise Exception(e.response.text)
        except requests.exceptions.ConnectTimeout as e:
            logger.critical(f'[request failed]-[URL: {url}]-[exc: {e}]')
            raise
        except Exception as e:
            logger.error(f'[request failed]-[URL: {url}]-[exc: {e}]')
            raise
        return req

    @staticmethod
    def create_account():

        private_key, address = generate_pair()
        account = Account(address)
        account.secret_key = private_key.hex()
        return account

    def get_balance(self, address: str) -> int:
        """
        the result must be * 10^(-18)
        1000000000000000000 = 1 egld
        """
        return self.elrond_proxy.get_account_balance(Address(address))

    def create_raw_transaction(self, sender: Account, receiver_address: str, value: str):
        tx = Transaction()
        sender.sync_nonce(self.elrond_proxy)  # update the nonce of sender account
        tx.nonce = sender.nonce
        tx.value = value
        tx.sender = sender.address.bech32()
        tx.receiver = receiver_address
        tx.gasPrice = 1000000000
        tx.gasLimit = 50000
        tx.chainID = '1'
        tx.version = '1'

        return tx

    @staticmethod
    def sing_transaction(sender: Account, raw_transaction: Transaction):
        raw_transaction.sign(sender)
        return raw_transaction

    def broadcast_transaction(self, transaction: Transaction):
        transaction.send(self.elrond_proxy)

    def get_transaction(self, tx_hash: str):
        return self.elrond_proxy.get_transaction(tx_hash)

    @staticmethod
    def get_block_transactions(block_height: int):
        """
        hyper block endpoint metachain blocks
        """
        req = ElrondHandler.make_request(
            url=ElrondHandler.urls['block'].format(block_height=block_height),
            method='get')
        data = req.json()
        transactions = []
        for tx in data['data']['hyperblock']['transactions']:
            if tx['type'] == 'normal':
                transaction = dict(
                    sender=tx['sender'],
                    reciever=tx['receiver'],
                    value=tx['value'],
                    hash=tx['hash']
                )
                transactions.append(transaction)
        pprint(transactions)
        return transactions

    @staticmethod
    def get_shard_block_transactions(shard: int, block_height: int):
        """
        shard block endpoint (shard 0, 1, 2, ...)
        """
        req = ElrondHandler.make_request(
            url=ElrondHandler.urls['shard_block'].format(shard_number=shard,
                                                         block_height=block_height),
            method='get')
        data = req.json()
        transactions = []
        for mini_block in data['data']['block']['miniBlocks']:
            for tx in mini_block['transactions']:
                if tx['type'] == 'normal':
                    transaction = dict(
                        sender=tx['sender'],
                        reciever=tx['receiver'],
                        value=tx['value'],
                        hash=tx['hash']
                    )
                    transactions.append(transaction)
        pprint(transactions)
        return transactions

    def get_block_height(self) -> int:
        return self.elrond_proxy.get_last_block_nonce(4294967295)
