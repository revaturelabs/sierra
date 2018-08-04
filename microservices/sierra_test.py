#!/usr/bin/env python3

import boto3
import pytest
from glob import glob


client = boto3.client('cloudformation')


@pytest.mark.parametrize('template', glob('templates/*.yml'))
def test_templates(template):
    with open(template) as f:
        client.validate_template(TemplateBody=f.read())


if __name__ == '__main__':
    pytest.main()
