"""Generate a CloudFormation template for microservices.
"""

import argparse
import json
import sys

from sierra.config import parse
from sierra.template import build_template
from sierra.utils import AttrDict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-f', '--file', type=str,
                        default='Sierrafile',
                        help='specify the Sierrafile to use')
    parser.add_argument('-o', '--out', type=argparse.FileType('w'),
                        default=sys.stdout,
                        help='a file to write output into')
    parser.add_argument('--format', choices=['yaml', 'json'],
                        default='yaml',
                        help='specify the output file format')
    parser.add_argument('--compact', action='store_true',
                        help='make output compact (only for json)')

    args = parser.parse_args()

    try:
        with open(args.file) as f:
            raw_sierrafile = json.load(f, object_hook=AttrDict)
    except FileNotFoundError:
        parser.print_help()
        parser.exit()

    sierrafile = parse(raw_sierrafile)
    template = build_template(sierrafile)

    if args.format == 'json':
        result = template.to_json()
        if args.compact:
            result = json.loads(result)
            result = json.dumps(result, separators=(',', ':'))
    else:
        result = template.to_yaml()

    print(result, file=args.out)


if __name__ == '__main__':
    main()
