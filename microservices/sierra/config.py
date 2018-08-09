from troposphere import Ref, Sub
from .template import ELB_NAME
from .utils import AttrDict


DEFAULTS = AttrDict({
    'container': AttrDict({
        'count': 1,
        'cpu': 128,
        'memory': 256,
    }),
    'pipeline': AttrDict({
        'enable': False,
    }),
})


def parse(raw_sierrafile):
    def update(old, new):
        for k, v in new.items():
            if isinstance(v, dict):
                old[k] = update(old.get(k, AttrDict()), v)
            else:
                old.setdefault(k, v)
        return old

    environment = raw_sierrafile.get('environment', {})
    extra_params, env_vars = [], {}

    for name, value in environment.items():
        if value is None:
            identifier = 'EnvironmentVariable' + str(len(extra_params))
            env_vars[name] = Ref(identifier)
            extra_params.append((identifier, name))
        elif isinstance(value, str):
            if '{ENDPOINT}' in value:
                value = Sub(value.format(ENDPOINT=f'${{{ELB_NAME}.DNSName}}'))
            env_vars[name] = value
        else:
            raise TypeError()

    defaults = raw_sierrafile.get('default', {})
    services = raw_sierrafile['services']

    for name, service in services.items():
        if 'pipeline' in service:
            service.pipeline.enable = True

        update(service, defaults)
        update(service, DEFAULTS)

        for env_var in service.get('environment', []):
            if env_var not in environment:
                raise ValueError()

    return AttrDict(
        extra_params=extra_params,
        env_vars=env_vars,
        services=services,
    )
