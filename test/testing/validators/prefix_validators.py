from SampleService.core.validator.builtin import _check_unknown_keys, _get_keys


def prefix_validator_test_builder(cfg):
    arg = cfg['fail_on_arg']

    def val(prefix, key, args):
        if arg in args:
            return f'{prefix}, {key}, {dict(sorted(args.items()))}'

    return val


def prefix_validator_string_builder(cfg):
    """
    Build a validation callable that performs string checking based on the following rules:

    If the 'keys' parameter is specified it must contain a string or a list of strings. The
    provided string(s) are used by the returned callable to query the metadata map.
    If any of the values for the provided keys are not strings, an error is returned. If the
    `max-len` parameter is provided, the value of which must be an integer, the values' lengths
    must be less than 'max-len'. If the 'required' parameter's value is truthy, an error is
    thrown if any of the keys in the 'keys' parameter do not exist in the map, athough the
    values may be None.

    If the 'keys' parameter is not provided, 'max-len' must be provided, in which case all
    the keys and string values in the metadata value map are checked against the max-value.
    Non-string values are ignored.

    :param d: the configuration map for the callable.
    :returns: a callable that validates metadata maps.
    """
    # no reason to require max-len, could just check all values are strings. YAGNI for now
    _check_unknown_keys(cfg, {'max-len', 'required', 'keys'})
    if 'max-len' not in cfg:
        maxlen = None
    else:
        try:
            maxlen = int(cfg['max-len'])
        except ValueError:
            raise ValueError('max-len must be an integer')
        if maxlen < 1:
            raise ValueError('max-len must be > 0')

    required = cfg.get('required') == 'true'

    # The validator spec may provide an array of "keys", which if provided, will require that
    # they be keys of the value, and this validation spec will be applied to them.
    keys = _get_keys(cfg)
    if keys:
        # Handles case of the keys being provided by the validator itself. Typically
        # either 'value' or 'unit'.
        def string_validator(_prefixKey: str, _key: str, d1):
            for k in keys:
                if required and k not in d1:
                    return {'subkey': str(k), 'message': f'Required key {k} is missing'}
                v = d1.get(k)
                if v is not None and type(v) != str:
                    return {'subkey': str(k), 'message': f'Metadata value at key {k} is not a string'}
                if v and maxlen and len(v) > maxlen:
                    return {'subkey': str(k),
                            'message': f'Metadata value at key {k} is longer than max length of {maxlen}'}
            return None
    elif maxlen:
        # If no keys are provided, both the key and the value are constrained.
        # TODO: keys should be constrained globally, imo.
        def string_validator(_prefixKey: str, _key: str, d1):
            for k, v in d1.items():
                if len(k) > maxlen:
                    return {'subkey': str(k), 'message': f'Metadata contains key longer than max length of {maxlen}'}
                if type(v) == str:
                    if len(v) > maxlen:
                        return {'subkey': str(k),
                                'message': f'Metadata value at key {k} is longer than max length of {maxlen}'}
            return None
    else:
        raise ValueError('If the keys parameter is not specified, max-len must be specified')
    return string_validator
