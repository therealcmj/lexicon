from __future__ import absolute_import

from builtins import object
import importlib
import os
import tldextract

from lexicon.common.options_handler import env_auth_options
from lexicon.config import ConfigurationResolver, DictConfigFeeder
from lexicon.config import non_interactive_config_resolver, legacy_config_resolver

# From providers import Example
class Client(object):
    def __init__(self, config = None):
        if not config:
            # If there is not config specified, we load a non-interactive configuration.
            self.config = non_interactive_config_resolver()
        elif not isinstance(config, ConfigurationResolver):
            # If config is not a ConfigurationResolver, we are in a legacy situation.
            # We protect this part of the Client API.
            self.config = legacy_config_resolver(config)
        else:
            self.config = config

        # Validate configuration
        self._validate_config()

        runtime_config = {}

        # Process domain, strip subdomain
        domain_parts = tldextract.extract(self.config.resolve('lexicon:domain'))
        runtime_config['domain'] = '{0}.{1}'.format(domain_parts.domain, domain_parts.suffix)

        if self.config.resolve('lexicon:delegated'):
            # handle delegated domain
            delegated = self.config.resolve('lexicon:delegated').rstrip('.')
            if delegated != runtime_config.get('domain'):
                # convert to relative name
                if delegated.endswith(runtime_config.get('domain')):
                    delegated = delegated[:-len(runtime_config.get('domain'))]
                    delegated = delegated.rstrip('.')
                # update domain
                runtime_config['domain'] = '{0}.{1}'.format(delegated, runtime_config.get('domain'))

        self.action = self.config.resolve('lexicon:action')
        self.provider_name = self.config.resolve('lexicon:provider_name') or self.config.resolve('lexicon:provider')

        self.config.add_config_feeder(DictConfigFeeder(runtime_config), 0)

        provider_module = importlib.import_module('lexicon.providers.' + self.provider_name)
        provider_class = getattr(provider_module, 'Provider')
        self.provider = provider_class(self.config)

    def execute(self):
        self.provider.authenticate()
        identifier = self.config.resolve('lexicon:identifier')
        type = self.config.resolve('lexicon:type')
        name = self.config.resolve('lexicon:name')
        content = self.config.resolve('lexicon:content')

        if self.action == 'create':
            return self.provider.create_record(type, name, content)

        elif self.action == 'list':
            return self.provider.list_records(type, name, content)

        elif self.action == 'update':
            return self.provider.update_record(identifier, type, name, content)

        elif self.action == 'delete':
            return self.provider.delete_record(identifier, type, name, content)

    def _validate_config(self):
        if not self.config.resolve('lexicon:provider_name'):
            raise AttributeError('provider_name')
        if not self.config.resolve('lexicon:action'):
            raise AttributeError('action')
        if not self.config.resolve('lexicon:domain'):
            raise AttributeError('domain')
        if not self.config.resolve('lexicon:type'):
            raise AttributeError('type')
