import logging
import os
import re
import yaml

LOGGER = logging.getLogger(__name__)

class ConfigurationResolver(object):
    """
    Highly customizable configuration resolver object, that gets configuration parameters
    from various sources with a precedence order. Sources and their priority are configured 
    by calling the with* methods of this object, in the decreasing priority order.

    A configuration parameter can be retrieved using the resolve() method. The configuration parameter
    key needs to conform to a namespace, whose delimeters is ':'. Two namespaces will be used in 
    the context of Lexicon:
        * the parameters relevant for Lexicon itself: 'lexicon:global_parameter'
        * the parameters specific to a DNS provider: 'lexicon:cloudflare:cloudflare_parameter'

    Example:
        # This will resolve configuration parameters from environment variables, 
        # then from a configuration file named '/my/path/to/lexicon.yml'.
        $ from lexicon.config import Config
        $ config = Config()
        $ config.with_env().with_config_file()
        $ print(config.resolve('lexicon:delegated'))
        $ print(config.resolve('lexicon:cloudflare:auth_token))

    Config can resolve parameters for Lexicon and providers from:
        * environment variables
        * arguments parsed by ArgParse library
        * YAML configuration files, generic or specific to a provider
        * any object implementing the underlying ConfigFeeder class

    Each parameter will be resolved against each source, and value from the higher priority source
    is returned. If a parameter could not be resolve by any source, then None will be returned.
    """

    def __init__(self):
        super(ConfigurationResolver, self).__init__()
        self._config_feeders = []

    def resolve(self, config_key):
        """
        Resolve the value of the given config parameter key. Key must be correctly scoped for Lexicon, and
        optionally for the DNS provider for which the parameter is consumed. For instance:
            * config.resolve('lexicon:delegated') will get the delegated config parameter for Lexicon
            * config.resolve('lexicon:cloudflare:auth_token') will get 
            the auth_token config parameter consumed by cloudflare DNS provider.

        Value is resolved against each configured source, and value from the highest priority source
        is returned. None will be returned if the given config parameter key could not be resolved
        from any source.
        """
        for config_feeder in self._config_feeders:
            value = config_feeder.feed(config_key)
            if value:
                return value

        return None

    def add_config_feeder(self, config_feeder, position = None):
        self._config_feeders.insert(position if position is not None else len(self._config_feeders), config_feeder)

    def with_config_feeder(self, config_feeder):
        """
        Configure current resolver to use the provided ConfigFeeder instance to be used as a source.
        See documentation of ConfigFeeder to see how to implement correctly a ConfigFeeder.
        """
        self.add_config_feeder(config_feeder)
        return self

    def with_env(self):
        """
        Configure current resolver to use available environment variables as a source.
        Only environment variables starting with 'LEXICON' or 'LEXICON_[PROVIDER]' 
        will be taken into account.
        """
        return self.with_config_feeder(EnvironmentConfigFeeder())

    def with_args(self, argparse_namespace):
        """
        Configure current resolver to use a Namespace object given by a ArgParse instance
        using arg_parse() as a source. This method is typically used to allow a ConfigurationResolver
        to get parameters from the command line.

        It is assumed that the argument parser have already checked that provided arguments are
        valid for Lexicon or the current provider. No further namespace check on parameter keys will
        be done here. Meaning that if 'lexicon:cloudflare:auth_token' is asked, any auth_token present
        in the given Namespace object will be returned.
        """
        return self.with_config_feeder(ArgsConfigFeeder(argparse_namespace))

    def with_dict(self, dict_object):
        """
        Configure current resolver to use the given dict object, scoped to lexicon namespace.
        
        Example of valid dict object for lexicon:
            {
                'delegated': 'onedelegated',
                'cloudflare': {
                    'auth_token': 'SECRET_TOKEN'
                }
            }
            => Will define properties 'lexicon:delegated' and 'lexicon:cloudflare:auth_token'
        """
        return self.with_config_feeder(DictConfigFeeder(dict_object))

    def with_config_file(self, file_path):
        """
        Configure current resolver to use a YAML configuration file specified on the given path.
        This file provides configuration parameters for Lexicon and any DNS provider.

        Typical format is:
            $ cat lexicon.yml
            # Will define properties 'lexicon:delegated' and 'lexicon:cloudflare:auth_token'
            delegated: 'onedelegated'
            cloudflare:
            auth_token: SECRET_TOKEN
        """
        return self.with_config_feeder(FileConfigFeeder(file_path))

    def with_provider_config_file(self, provider_name, file_path):
        """
        Configure current resolver to use a YAML configuration file specified on the given path.
        This file provides configuration parameters for a DNS provider exclusively.

        Typical format is:
            $ cat lexicon_cloudflare.yml
            # Will define properties 'lexicon:cloudflare:auth_token' and 'lexicon:cloudflare:auth_username'
            auth_token: SECRET_TOKEN
            auth_username: USERNAME

        NB: If file_path is not specified, '/etc/lexicon/lexicon_[provider].yml' will be taken
        by default, with [provider] equals to the given provider_name parameter.
        """
        return self.with_config_feeder(ProviderFileConfigFeeder(provider_name, file_path))

    def with_config_dir(self, dir_path):
        """
        Configure current resolver to use every valid YAML configuration files available in the
        given directory path. To be taken into account, a configuration file must conform to the
        following naming convention:
            * 'lexicon.yml' for a global Lexicon config file (see with_config_file doc)
            * 'lexicon_[provider].yml' for a DNS provider specific configuration file, with
            [provider] equals to the DNS provider name (see with_provider_config_file doc)

        Example:
            $ ls /etc/lexicon
            lexicon.yml # global Lexicon configuration file
            lexicon_cloudflare.yml # specific configuration file for clouflare DNS provder
        """
        lexicon_provider_config_files = []
        lexicon_config_files = []

        for path in os.listdir(dir_path):
            path = os.path.join(dir_path, path)
            if os.path.isfile(path):
                basename = os.path.basename(path)
                search = re.search(r'^lexicon(?:_(\w+)|)\.yml$', basename)
                if search:
                    provider = search.group(1)
                    if provider:
                        lexicon_provider_config_files.append((provider, path))
                    else:
                        lexicon_config_files.append(path)

        for lexicon_provider_config_file in lexicon_provider_config_files:
            self.with_provider_config_file(lexicon_provider_config_file[0], lexicon_provider_config_file[1])

        for lexicon_config_file in lexicon_config_files:
            self.with_config_file(lexicon_config_file)

        return self

    def with_legacy_dict(self, legacy_dict_object):
        LOGGER.warning('Legacy configuration object has been used to load the ConfigurationResolver.')
        return self.with_config_feeder(LegacyDictConfigFeeder(legacy_dict_object))

class ConfigFeeder(object):
    """
    Base class to implement a configuration source for ResolverConfig.
    The relevant method to override is feed(self, config_parameter).
    """

    def feed(self, config_parameter):
        """
        Using the given config_parameter value (in the form of 'lexicon:config_key' or 
        'lexicon:[provider]:config_key'), try to get the associated value.

        None must be returned if no value could be found.

        Must be implemented by each ConfigFeeder concrete child class.
        """
        raise NotImplementedError('The method feed must be implemented in the concret sub-classes.')

class EnvironmentConfigFeeder(ConfigFeeder):

    def __init__(self):
        super(EnvironmentConfigFeeder, self).__init__()
        self._parameters = {}
        for (key, value) in os.environ.items():
            if key.startswith('LEXICON_'):
                self._parameters[key] = value

    def feed(self, config_parameter):
        # First try, with a direct conversion of the config_parameter: 
        #   * lexicon:provider:auth_my_config => LEXICON_PROVIDER_AUTH_MY_CONFIG
        #   * lexicon:provider:my_other_config => LEXICON_PROVIDER_AUTH_MY_OTHER_CONFIG
        #   * lexicon:my_global_config => LEXICON_MY_GLOBAL_CONFIG
        environment_variable = re.sub(':', '_', config_parameter).upper()
        value = self._parameters.get(environment_variable, None)
        if value:
            return value

        # Second try, with the legacy naming convention for specific provider config: 
        #   * lexicon:provider:auth_my_config => LEXICON_PROVIDER_MY_CONFIG
        # Users get a warning about this deprecated usage.
        environment_variable_legacy = re.sub(r'(.*)_AUTH_(.*)', r'\1_\2', environment_variable).upper()
        value = self._parameters.get(environment_variable_legacy, None)
        if value:
            LOGGER.warning('Warning: Use of environment variable {0} is deprecated. Try {1} instead.'
            .format(environment_variable_legacy, environment_variable))
            return value

        return None

class ArgsConfigFeeder(ConfigFeeder):

    def __init__(self, namespace):
        super(ArgsConfigFeeder, self).__init__()
        self._parameters = vars(namespace)

    def feed(self, config_key):
        # We assume here that the namespace provided has already done its job,
        # by validating that all given parameters are relevant for Lexicon or the current provider.
        # So we ignore the namespaces 'lexicon:' and 'lexicon:provider' in given config key.
        splitted_config_key = config_key.split(':')

        return self._parameters.get(splitted_config_key[-1], None)

class DictConfigFeeder(ConfigFeeder):

    def __init__(self, dict_object):
        super(DictConfigFeeder, self).__init__()
        self._parameters = dict_object

    def feed(self, config_key):
        splitted_config_key = config_key.split(':')
        # Note that we ignore 'lexicon:' in the iteration,
        # as the dict object is already scoped to lexicon.
        cursor = self._parameters
        for current in splitted_config_key[1:-1]:
            cursor = cursor.get(current, {})

        return cursor.get(splitted_config_key[-1], None)

class FileConfigFeeder(DictConfigFeeder):

    def __init__(self, file_path):
        with open(file_path, 'r') as stream:
            yaml_object = yaml.load(stream) or {}

        super(FileConfigFeeder, self).__init__(yaml_object)

class ProviderFileConfigFeeder(FileConfigFeeder):

    def __init__(self, provider_name, file_path):
        super(ProviderFileConfigFeeder, self).__init__(file_path)
        # Scope the loaded config file into provider namespace
        self._parameters = {provider_name: self._parameters}

class LegacyDictConfigFeeder(DictConfigFeeder):

    def __init__(self, dict_object):
        provider_name = dict_object.get('provider_name')
        if not provider_name:
            raise AttributeError('Error, key provider_name is not defined.'
                                 'LegacyDictConfigFeeder cannot scope correctly '
                                 'the provider specific options.')

        generic_parameters = [
            'domain', 'action', 'provider_name', 'delegated', 'identifier', 'type' , 'name',
            'content', 'ttl', 'priority', 'log_level', 'output']

        provider_options = {}
        refactor_dict_object = {}
        refactor_dict_object[provider_name] = provider_options

        for (key, value) in dict_object.items():
            if key not in generic_parameters:
                provider_options[key] = value
            else:
                refactor_dict_object[key] = value

        super(LegacyDictConfigFeeder, self).__init__(refactor_dict_object)

def non_interactive_config_resolver():
    return ConfigurationResolver().with_env().with_config_dir(os.getcwd())

def legacy_config_resolver(legacy_dict):
    """
    With the old legacy approach, we juste got a plain configuration dict object.
    Custom logic was to enrich this configuration with env variables.

    This function create a resolve that respect the expected behavior, by using the relevant
    ConfigFeeders, and we add the config files from working directory.
    """
    return ConfigurationResolver().with_legacy_dict(legacy_dict).with_env().with_config_dir(os.getcwd())