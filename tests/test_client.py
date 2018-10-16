import lexicon.client
import pytest
import os

from lexicon.config import ConfigurationResolver

def test_Client_basic_init():
    options = {
        'provider_name': 'base',
        'action': 'list',
        'domain': 'example.com',
        'type': 'TXT'
    }
    client = lexicon.client.Client(ConfigurationResolver().with_dict(options))

    assert client.provider_name == options['provider_name']
    assert client.action == options['action']
    assert client.config.resolve('lexicon:domain') == options['domain']
    assert client.config.resolve('lexicon:type') == options['type']

def test_Client_legacy_init():
    options = {
        'provider_name': 'base',
        'action': 'list',
        'domain': 'example.com',
        'type': 'TXT'
    }
    client = lexicon.client.Client(options)

    assert client.provider_name == options['provider_name']
    assert client.action == options['action']
    assert client.config.resolve('lexicon:domain') == options['domain']
    assert client.config.resolve('lexicon:type') == options['type']

def test_Client_init_when_domain_includes_subdomain_should_strip():
    options = {
        'provider_name':'base',
        'action': 'list',
        'domain': 'www.example.com',
        'type': 'TXT'
    }
    client = lexicon.client.Client(options)

    assert client.provider_name == options['provider_name']
    assert client.action == options['action']
    assert client.config.resolve('lexicon:domain') == 'example.com'
    assert client.config.resolve('lexicon:type') == options['type']

def test_Client_init_with_delegated_domain_name():
    options = {
        'provider_name':'base',
        'action': 'list',
        'domain': 'www.sub.example.com',
        'delegated': 'sub',
        'type': 'TXT'
    }
    client = lexicon.client.Client(options)

    assert client.provider_name == options['provider_name']
    assert client.action == options['action']
    assert client.config.resolve('lexicon:domain') == "sub.example.com"
    assert client.config.resolve('lexicon:type') == options['type']

def test_Client_init_with_delegated_domain_fqdn():
    options = {
        'provider_name':'base',
        'action': 'list',
        'domain': 'www.sub.example.com',
        'delegated': 'sub.example.com',
        'type': 'TXT'
    }
    client = lexicon.client.Client(options)

    assert client.provider_name == options['provider_name']
    assert client.action == options['action']
    assert client.config.resolve('lexicon:domain') == "sub.example.com"
    assert client.config.resolve('lexicon:type') == options['type']

def test_Client_init_with_same_delegated_domain_fqdn():
    options = {
        'provider_name':'base',
        'action': 'list',
        'domain': 'www.example.com',
        'delegated': 'example.com',
        'type': 'TXT'
    }
    client = lexicon.client.Client(options)

    assert client.provider_name == options['provider_name']
    assert client.action == options['action']
    assert client.config.resolve('lexicon:domain') == "example.com"
    assert client.config.resolve('lexicon:type') == options['type']

def test_Client_init_when_missing_provider_should_fail():
    options = {
        'action': 'list',
        'domain': 'example.com',
        'type': 'TXT'
    }
    with pytest.raises(AttributeError):
        lexicon.client.Client(options)

def test_Client_init_when_missing_action_should_fail():
    options = {
        'provider_name':'base',
        'domain': 'example.com',
        'type': 'TXT'
    }
    with pytest.raises(AttributeError):
        lexicon.client.Client(options)

def test_Client_init_when_missing_domain_should_fail():
    options = {
        'provider_name':'base',
        'action': 'list',
        'type': 'TXT'
    }
    with pytest.raises(AttributeError):
        lexicon.client.Client(options)

def test_Client_init_when_missing_type_should_fail():
    options = {
        'provider_name':'base',
        'action': 'list',
        'domain': 'example.com',
    }
    with pytest.raises(AttributeError):
        lexicon.client.Client(options)

def test_Client_parse_env_with_no_keys_should_do_nothing(monkeypatch):
    if os.environ.get('LEXICON_CLOUDFLARE_TOKEN'):
        monkeypatch.delenv('LEXICON_CLOUDFLARE_TOKEN')
    if os.environ.get('LEXICON_CLOUDFLARE_USERNAME'):
        monkeypatch.delenv('LEXICON_CLOUDFLARE_USERNAME')
    options = {
        'provider_name':'cloudflare',
        'action': 'list',
        'domain': 'www.example.com',
        'type': 'TXT'
    }
    client = lexicon.client.Client(options)


    assert client.provider_name == options['provider_name']
    assert client.action == options['action']
    assert client.config.resolve('lexicon:domain') == 'example.com'
    assert client.config.resolve('lexicon:type') == options['type']
    assert client.config.resolve('lexicon:cloudflare:auth_token') == None
    assert client.config.resolve('lexicon:cloudflare:auth_username') == None

def test_Client_parse_env_with_auth_keys(monkeypatch):
    monkeypatch.setenv('LEXICON_CLOUDFLARE_TOKEN','test-token')
    monkeypatch.setenv('LEXICON_CLOUDFLARE_USERNAME','test-username@example.com')
    options = {
        'provider_name':'cloudflare',
        'action': 'list',
        'domain': 'www.example.com',
        'type': 'TXT'
    }
    client = lexicon.client.Client(options)


    assert client.provider_name == options['provider_name']
    assert client.action == options['action']
    assert client.config.resolve('lexicon:domain') == 'example.com'
    assert client.config.resolve('lexicon:type') == options['type']
    assert client.config.resolve('lexicon:cloudflare:auth_token') == 'test-token'
    assert client.config.resolve('lexicon:cloudflare:auth_username') == 'test-username@example.com'

#TODO: add tests for Provider loading?