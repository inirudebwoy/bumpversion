import argparse
import re
import io
import os.path
import warnings

try:
    from configparser import RawConfigParser, NoOptionError
except ImportError:
    from ConfigParser import RawConfigParser, NoOptionError

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

import bumpversion

DEFAULT_PARSE = '(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)'
DEFAULT_VERSION = '{new_version}'
DEFAULT_SERIALIZE = [str('{major}.{minor}.{patch}')]
DEFAULT_SEARCH = '{current_version}'


def exists(path):
    return os.path.exists(path)

def get_parser():
    config = RawConfigParser('')
    # don't transform keys to lowercase (which would be the default)
    config.optionxform = lambda option: option
    config.add_section('bumpversion')
    

    
def save(filename, context):
    config = get_parser()
    
    config.set('bumpversion', 'new_version', context.new_version)

    for key, value in config.items('bumpversion'):
        bumpversion.logger_list.info("{}={}".format(key, value))

    config.remove_option('bumpversion', 'new_version')

    config.set('bumpversion', 'current_version', context.new_version)

    try:
        write_to_config_file = (not context.dry_run) and exists(filename)

        bumpversion.logger.info("{} to config file {}:".format(
            "Would write" if not write_to_config_file else "Writing",
            filename,
        ))

        new_config = StringIO()
        config.write(new_config)
        bumpversion.logger.info(new_config.getvalue())

        if write_to_config_file:
            with io.open(filename, 'wb') as f:
                f.write(new_config.getvalue().encode('utf-8'))

    except UnicodeEncodeError:
        warnings.warn(
            "Unable to write UTF-8 to config file, because of an old configparser version. "
            "Update with `pip install --upgrade configparser`."
        )


def get_name(context):
    explicit_config = hasattr(context, 'config_file')

    if explicit_config:
        name = context.config_file
    elif not os.path.exists('.bumpversion.cfg') and \
            os.path.exists('setup.cfg'):
        name = 'setup.cfg'
    else:
        name = '.bumpversion.cfg'
    return name

        
def load(filename, context, defaults):
    config = RawConfigParser('')
    # don't transform keys to lowercase (which would be the default)
    config.optionxform = lambda option: option
    config.add_section('bumpversion')

    part_configs = {}
    files = []

    if exists(filename):

        bumpversion.logger.info("Reading config file {}:".format(filename))
        bumpversion.logger.info(io.open(filename, 'rt', encoding='utf-8').read())

        config.readfp(io.open(filename, 'rt', encoding='utf-8'))

        log_config = StringIO()
        config.write(log_config)

        if 'files' in dict(config.items("bumpversion")):
            warnings.warn(
                "'files =' configuration is will be deprecated, please use [bumpversion:file:...]",
                PendingDeprecationWarning
            )

        defaults.update(dict(config.items("bumpversion")))

        for listvaluename in ("serialize",):
            try:
                value = config.get("bumpversion", listvaluename)
                defaults[listvaluename] = list(filter(None, (x.strip() for x in value.splitlines())))
            except NoOptionError:
                pass  # no default value then ;)

        for boolvaluename in ("commit", "tag", "dry_run"):
            try:
                defaults[boolvaluename] = config.getboolean(
                    "bumpversion", boolvaluename)
            except NoOptionError:
                pass  # no default value then ;)

        for section_name in config.sections():
            section_name_match = re.compile("^bumpversion:(file|part):(.+)").match(section_name)
            if not section_name_match:
                continue

            section_prefix, section_value = section_name_match.groups()
            section_config = dict(config.items(section_name))

            if section_prefix == "part":

                ThisVersionPartConfiguration = bumpversion.NumericVersionPartConfiguration

                if 'values' in section_config:
                    section_config['values'] = list(filter(None, (x.strip() for x in section_config['values'].splitlines())))
                    ThisVersionPartConfiguration = bumpversion.ConfiguredVersionPartConfiguration

                part_configs[section_value] = ThisVersionPartConfiguration(**section_config)

            elif section_prefix == "file":

                filename = section_value

                if 'serialize' in section_config:
                    section_config['serialize'] = list(filter(None, (x.strip() for x in section_config['serialize'].splitlines())))

                section_config['part_configs'] = part_configs

                if not 'parse' in section_config:
                    section_config['parse'] = defaults.get("parse", DEFAULT_PARSE)

                if not 'serialize' in section_config:
                    section_config['serialize'] = defaults.get('serialize', DEFAULT_SERIALIZE)

                if not 'search' in section_config:
                    section_config['search'] = defaults.get("search", DEFAULT_SEARCH)

                if not 'replace' in section_config:
                    section_config['replace'] = defaults.get("replace", DEFAULT_VERSION)

                files.append(bumpversion.ConfiguredFile(filename,
                                                        bumpversion.VersionConfig(**section_config)))

    else:
        message = "Could not read config file at {}".format(filename)
        if hasattr(context, 'config_file'):
            raise argparse.ArgumentTypeError(message)
        else:
            bumpversion.logger.info(message)

    return part_configs, files, config, defaults
