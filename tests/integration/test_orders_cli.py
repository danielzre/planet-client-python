# Copyright 2022 Planet Labs, PBC.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
'''Test Orders CLI'''
import copy
from http import HTTPStatus
import json
from pathlib import Path
from unittest.mock import Mock

import click
from click.testing import CliRunner
import httpx
import pytest
import respx

from planet.cli import cli

TEST_URL = 'http://MockNotRealURL/api/path'
TEST_DOWNLOAD_URL = f'{TEST_URL}/download'
TEST_ORDERS_URL = f'{TEST_URL}/orders/v2'

# NOTE: These tests use a lot of the same mocked responses as test_orders_api.


@pytest.fixture
def invoke():

    def _invoke(extra_args, runner=None):
        runner = runner or CliRunner()
        args = ['orders', '--base-url', TEST_URL] + extra_args
        return runner.invoke(cli.main, args=args)

    return _invoke


def test_split_list_arg_empty_string():
    with pytest.raises(click.exceptions.BadParameter):
        cli.orders.split_list_arg(None, None, '')


def test_split_list_arg_None():
    assert cli.orders.split_list_arg(None, None, None) is None


@respx.mock
def test_cli_orders_list_basic(invoke, order_descriptions):
    next_page_url = TEST_ORDERS_URL + '/blob/?page_marker=IAmATest'
    order1, order2, order3 = order_descriptions

    page1_response = {
        "_links": {
            "_self": "string", "next": next_page_url
        },
        "orders": [order1, order2]
    }
    mock_resp1 = httpx.Response(HTTPStatus.OK, json=page1_response)
    respx.get(TEST_ORDERS_URL).return_value = mock_resp1

    page2_response = {"_links": {"_self": next_page_url}, "orders": [order3]}
    mock_resp2 = httpx.Response(HTTPStatus.OK, json=page2_response)
    respx.get(next_page_url).return_value = mock_resp2

    result = invoke(['list'])
    assert not result.exception
    assert json.dumps([order1, order2, order3]) + '\n' == result.output


@respx.mock
def test_cli_orders_list_empty(invoke):
    page1_response = {"_links": {"_self": "string"}, "orders": []}
    mock_resp = httpx.Response(HTTPStatus.OK, json=page1_response)
    respx.get(TEST_ORDERS_URL).return_value = mock_resp

    result = invoke(['list'])
    assert not result.exception
    assert [] == json.loads(result.output)


@respx.mock
def test_cli_orders_list_state(invoke, order_descriptions):
    list_url = TEST_ORDERS_URL + '?state=failed'

    order1, order2, _ = order_descriptions

    page1_response = {
        "_links": {
            "_self": "string"
        }, "orders": [order1, order2]
    }
    mock_resp = httpx.Response(HTTPStatus.OK, json=page1_response)
    respx.get(list_url).return_value = mock_resp

    # if the value of state doesn't get sent as a url parameter,
    # the mock will fail and this test will fail
    result = invoke(['list', '--state', 'failed'])
    assert not result.exception
    assert [order1, order2] == json.loads(result.output)


@respx.mock
@pytest.mark.parametrize("limit,limited_list_length", [(None, 100), (0, 102),
                                                       (1, 1)])
def test_cli_orders_list_limit(invoke,
                               order_descriptions,
                               limit,
                               limited_list_length):
    # Creating 102 (3x34) order descriptions
    long_order_descriptions = order_descriptions * 34

    all_orders = {}
    for x in range(1, len(long_order_descriptions) + 1):
        all_orders["order{0}".format(x)] = long_order_descriptions[x - 1]

    page1_response = {
        "_links": {
            "_self": "string"
        },
        "orders": [
            all_orders['order%s' % num]
            for num in range(1, limited_list_length + 1)
        ]
    }
    mock_resp = httpx.Response(HTTPStatus.OK, json=page1_response)

    # limiting is done within the client, no change to api call
    respx.get(TEST_ORDERS_URL).return_value = mock_resp

    result = invoke(['list', '--limit', limit])
    assert not result.exception
    assert len(json.loads(result.output)) == limited_list_length


@respx.mock
def test_cli_orders_list_pretty(invoke, monkeypatch, order_description):
    mock_echo_json = Mock()
    monkeypatch.setattr(cli.orders, 'echo_json', mock_echo_json)

    page1_response = {
        "_links": {
            "_self": "string"
        }, "orders": [order_description]
    }
    mock_resp = httpx.Response(HTTPStatus.OK, json=page1_response)
    respx.get(TEST_ORDERS_URL).return_value = mock_resp

    result = invoke(['list', '--pretty'])
    assert not result.exception
    mock_echo_json.assert_called_once_with([order_description], True)


# TODO: add tests for "get --pretty" (gh-491).
@respx.mock
def test_cli_orders_get(invoke, oid, order_description):
    get_url = f'{TEST_ORDERS_URL}/{oid}'
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.get(get_url).return_value = mock_resp

    result = invoke(['get', oid])
    assert not result.exception
    assert order_description == json.loads(result.output)


@respx.mock
def test_cli_orders_get_id_not_found(invoke, oid):
    get_url = f'{TEST_ORDERS_URL}/{oid}'
    error_json = {"message": "Error message"}
    mock_resp = httpx.Response(404, json=error_json)
    respx.get(get_url).return_value = mock_resp

    result = invoke(['get', oid])
    assert result.exception
    assert 'Error: {"message": "Error message"}\n' == result.output


# TODO: add tests for "cancel --pretty" (gh-491).
@respx.mock
def test_cli_orders_cancel(invoke, oid, order_description):
    cancel_url = f'{TEST_ORDERS_URL}/{oid}'
    order_description['state'] = 'cancelled'
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.put(cancel_url).return_value = mock_resp

    result = invoke(['cancel', oid])
    assert not result.exception
    assert str(mock_resp.json()) + '\n' == result.output


@respx.mock
def test_cli_orders_cancel_id_not_found(invoke, oid):
    cancel_url = f'{TEST_ORDERS_URL}/{oid}'
    error_json = {"message": "Error message"}
    mock_resp = httpx.Response(404, json=error_json)
    respx.put(cancel_url).return_value = mock_resp

    result = invoke(['cancel', oid])
    assert result.exception
    assert 'Error: {"message": "Error message"}\n' == result.output


# TODO: add tests for "wait --state" (gh-492) and "wait --pretty" (gh-491).
@respx.mock
def test_cli_orders_wait_default(invoke, order_description, oid):
    get_url = f'{TEST_ORDERS_URL}/{oid}'

    order_description2 = copy.deepcopy(order_description)
    order_description2['state'] = 'success'

    route = respx.get(get_url)
    route.side_effect = [
        httpx.Response(HTTPStatus.OK, json=order_description),
        httpx.Response(HTTPStatus.OK, json=order_description2)
    ]

    runner = CliRunner()
    result = invoke(['wait', '--delay', '0', oid], runner=runner)
    assert not result.exception
    assert result.output.endswith('success\n')


@respx.mock
def test_cli_orders_wait_max_attempts(invoke, order_description, oid):
    get_url = f'{TEST_ORDERS_URL}/{oid}'

    order_description2 = copy.deepcopy(order_description)
    order_description2['state'] = 'running'
    order_description3 = copy.deepcopy(order_description)
    order_description3['state'] = 'success'

    route = respx.get(get_url)
    route.side_effect = [httpx.Response(HTTPStatus.OK, json=order_description)]

    runner = CliRunner()
    result = invoke(['wait', '--delay', '0', '--max-attempts', '1', oid],
                    runner=runner)
    assert result.exception
    assert result.output.endswith(
        'Error: Maximum number of attempts (1) reached.\n')


@pytest.fixture
def mock_download_response(oid, order_description):

    def _func():
        # Mock an HTTP response for download
        order_description['state'] = 'success'
        dl_url1 = TEST_DOWNLOAD_URL + '/1?token=IAmAToken'
        dl_url2 = TEST_DOWNLOAD_URL + '/2?token=IAmAnotherToken'
        order_description['_links']['results'] = [{
            'location': dl_url1
        }, {
            'location': dl_url2
        }]

        get_url = f'{TEST_ORDERS_URL}/{oid}'
        mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
        respx.get(get_url).return_value = mock_resp

        mock_resp1 = httpx.Response(HTTPStatus.OK,
                                    json={'key': 'value'},
                                    headers={
                                        'Content-Type':
                                        'application/json',
                                        'Content-Disposition':
                                        'attachment; filename="m1.json"'
                                    })
        respx.get(dl_url1).return_value = mock_resp1

        mock_resp2 = httpx.Response(HTTPStatus.OK,
                                    json={'key2': 'value2'},
                                    headers={
                                        'Content-Type':
                                        'application/json',
                                        'Content-Disposition':
                                        'attachment; filename="m2.json"'
                                    })
        respx.get(dl_url2).return_value = mock_resp2

    return _func


# TODO: add test for --checksum (see gh-432).
@respx.mock
def test_cli_orders_download_default(invoke, mock_download_response, oid):
    mock_download_response()

    runner = CliRunner()
    with runner.isolated_filesystem() as folder:
        result = invoke(['download', oid], runner=runner)
        assert not result.exception

        # basic check of progress reporting
        assert 'm1.json' in result.output

        # Check that the files were downloaded and have the correct contents
        f1_path = Path(folder) / 'm1.json'
        assert json.load(open(f1_path)) == {'key': 'value'}
        f2_path = Path(folder) / 'm2.json'
        assert json.load(open(f2_path)) == {'key2': 'value2'}


@respx.mock
def test_cli_orders_download_dest(invoke, mock_download_response, oid):
    mock_download_response()

    runner = CliRunner()
    with runner.isolated_filesystem() as folder:
        dest_dir = Path(folder) / 'foobar'
        dest_dir.mkdir()
        result = invoke(['download', '--directory', 'foobar', oid],
                        runner=runner)
        assert not result.exception

        # Check that the files were downloaded to the custom directory
        f1_path = dest_dir / 'm1.json'
        assert json.load(open(f1_path)) == {'key': 'value'}
        f2_path = dest_dir / 'm2.json'
        assert json.load(open(f2_path)) == {'key2': 'value2'}


@respx.mock
def test_cli_orders_download_overwrite(invoke,
                                       mock_download_response,
                                       oid,
                                       write_to_tmp_json_file):
    mock_download_response()

    runner = CliRunner()
    with runner.isolated_filesystem() as folder:
        filepath = Path(folder) / 'm1.json'
        write_to_tmp_json_file({'foo': 'bar'}, filepath)

        # check the file doesn't get overwritten by default
        result = invoke(['download', oid], runner=runner)
        assert not result.exception
        assert json.load(open(filepath)) == {'foo': 'bar'}

        # check the file gets overwritten
        result = invoke(['download', '--overwrite', oid], runner=runner)
        assert not result.exception
        assert json.load(open(filepath)) == {'key': 'value'}


@respx.mock
def test_cli_orders_download_state(invoke, order_description, oid):
    get_url = f'{TEST_ORDERS_URL}/{oid}'

    order_description['state'] = 'running'
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.get(get_url).return_value = mock_resp

    runner = CliRunner()
    result = invoke(['download', oid], runner=runner)

    assert result.exception
    assert 'order state (running) is not a final state.' in result.output


# TODO: convert "create" tests to "request" tests (gh-366).
# TODO: add tests of "create --pretty" (gh-491).
@pytest.mark.parametrize(
    "id_string, expected_ids",
    [('4500474_2133707_2021-05-20_2419', ['4500474_2133707_2021-05-20_2419']),
     ('4500474_2133707_2021-05-20_2419,4500474_2133707_2021-05-20_2420',
      ['4500474_2133707_2021-05-20_2419', '4500474_2133707_2021-05-20_2420'])])
@respx.mock
def test_cli_orders_create_basic_success(expected_ids,
                                         id_string,
                                         invoke,
                                         order_description):
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.post(TEST_ORDERS_URL).return_value = mock_resp

    result = invoke([
        'create',
        '--name=test',
        f'--id={id_string}',
        '--bundle=analytic',
        '--item-type=PSOrthoTile'
    ])
    assert not result.exception
    assert order_description == json.loads(result.output)

    order_request = {
        "name":
        "test",
        "products": [{
            "item_ids": expected_ids,
            "item_type": "PSOrthoTile",
            "product_bundle": "analytic"
        }],
    }
    sent_request = json.loads(respx.calls.last.request.content)
    assert sent_request == order_request


def test_cli_orders_create_basic_item_type_invalid(invoke):
    result = invoke([
        'create',
        '--name=test',
        '--id=4500474_2133707_2021-05-20_2419',
        '--bundle=analytic',
        '--item-type=invalid'
    ])
    assert result.exception
    assert 'Error: Invalid value: item_type' in result.output


def test_cli_orders_create_id_empty(invoke):
    result = invoke([
        'create',
        '--name',
        'test',
        '--id',
        '',
        '--bundle',
        'analytic',
        '--item-type',
        'PSOrthoTile'
    ])
    assert result.exit_code
    assert 'Entry cannot be an empty string.' in result.output


@respx.mock
def test_cli_orders_create_clip(invoke,
                                geom_geojson,
                                order_description,
                                write_to_tmp_json_file):
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.post(TEST_ORDERS_URL).return_value = mock_resp

    aoi_file = write_to_tmp_json_file(geom_geojson, 'aoi.geojson')

    result = invoke([
        'create',
        '--name',
        'test',
        '--id',
        '4500474_2133707_2021-05-20_2419',
        '--bundle',
        'analytic',
        '--item-type',
        'PSOrthoTile',
        '--clip',
        aoi_file
    ])
    assert not result.exception

    order_request = {
        "name":
        "test",
        "products": [{
            "item_ids": ["4500474_2133707_2021-05-20_2419"],
            "item_type": "PSOrthoTile",
            "product_bundle": "analytic",
        }],
        "tools": [{
            'clip': {
                'aoi': geom_geojson
            }
        }]
    }
    sent_request = json.loads(respx.calls.last.request.content)
    assert sent_request == order_request


@respx.mock
def test_cli_orders_create_clip_featurecollection(invoke,
                                                  featurecollection_geojson,
                                                  geom_geojson,
                                                  order_description,
                                                  write_to_tmp_json_file):
    """Tests that the clip option takes in feature class geojson as well"""
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.post(TEST_ORDERS_URL).return_value = mock_resp

    fc_file = write_to_tmp_json_file(featurecollection_geojson, 'fc.geojson')

    result = invoke([
        'create',
        '--name',
        'test',
        '--id',
        '4500474_2133707_2021-05-20_2419',
        '--bundle',
        'analytic',
        '--item-type',
        'PSOrthoTile',
        '--clip',
        fc_file
    ])
    assert not result.exception

    order_request = {
        "name":
        "test",
        "products": [{
            "item_ids": ["4500474_2133707_2021-05-20_2419"],
            "item_type": "PSOrthoTile",
            "product_bundle": "analytic",
        }],
        "tools": [{
            'clip': {
                'aoi': geom_geojson
            }
        }]
    }
    sent_request = json.loads(respx.calls.last.request.content)
    assert sent_request == order_request


def test_cli_orders_create_clip_invalid_geometry(invoke,
                                                 point_geom_geojson,
                                                 write_to_tmp_json_file):
    aoi_file = write_to_tmp_json_file(point_geom_geojson, 'aoi.geojson')

    result = invoke([
        'create',
        '--name',
        'test',
        '--id',
        '4500474_2133707_2021-05-20_2419',
        '--bundle',
        'analytic',
        '--item-type',
        'PSOrthoTile',
        '--clip',
        aoi_file
    ])
    assert result.exception
    error_msg = ('Error: Invalid value: Invalid geometry type: ' +
                 'Point is not Polygon.')
    assert error_msg in result.output


def test_cli_orders_create_clip_and_tools(invoke,
                                          geom_geojson,
                                          write_to_tmp_json_file):
    # interestingly, it is important that both clip and tools
    # option values lead to valid json files
    aoi_file = write_to_tmp_json_file(geom_geojson, 'aoi.geojson')

    result = invoke([
        'create',
        '--name',
        'test',
        '--id',
        '4500474_2133707_2021-05-20_2419',
        '--bundle',
        'analytic',
        '--item-type',
        'PSOrthoTile',
        '--clip',
        aoi_file,
        '--tools',
        aoi_file
    ])
    assert result.exception
    assert "Specify only one of '--clip' or '--tools'" in result.output


@respx.mock
def test_cli_orders_create_cloudconfig(invoke,
                                       geom_geojson,
                                       order_description,
                                       write_to_tmp_json_file):
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.post(TEST_ORDERS_URL).return_value = mock_resp

    config_json = {
        'amazon_s3': {
            'aws_access_key_id': 'aws_access_key_id',
            'aws_secret_access_key': 'aws_secret_access_key',
            'bucket': 'bucket',
            'aws_region': 'aws_region'
        },
        'archive_type': 'zip'
    }
    config_file = write_to_tmp_json_file(config_json, 'config.json')

    result = invoke([
        'create',
        '--name',
        'test',
        '--id',
        '4500474_2133707_2021-05-20_2419',
        '--bundle',
        'analytic',
        '--item-type',
        'PSOrthoTile',
        '--cloudconfig',
        config_file
    ])
    assert not result.exception

    order_request = {
        "name":
        "test",
        "products": [{
            "item_ids": ["4500474_2133707_2021-05-20_2419"],
            "item_type": "PSOrthoTile",
            "product_bundle": "analytic",
        }],
        "delivery":
        config_json
    }
    sent_request = json.loads(respx.calls.last.request.content)
    assert sent_request == order_request


@respx.mock
def test_cli_orders_create_email(invoke, geom_geojson, order_description):
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.post(TEST_ORDERS_URL).return_value = mock_resp

    result = invoke([
        'create',
        '--name',
        'test',
        '--id',
        '4500474_2133707_2021-05-20_2419',
        '--bundle',
        'analytic',
        '--item-type',
        'PSOrthoTile',
        '--email'
    ])
    assert not result.exception

    order_request = {
        "name":
        "test",
        "products": [{
            "item_ids": ["4500474_2133707_2021-05-20_2419"],
            "item_type": "PSOrthoTile",
            "product_bundle": "analytic",
        }],
        "notifications": {
            "email": True
        }
    }
    sent_request = json.loads(respx.calls.last.request.content)
    assert sent_request == order_request


@respx.mock
def test_cli_orders_create_tools(invoke,
                                 geom_geojson,
                                 order_description,
                                 write_to_tmp_json_file):
    mock_resp = httpx.Response(HTTPStatus.OK, json=order_description)
    respx.post(TEST_ORDERS_URL).return_value = mock_resp

    tools_json = [{'clip': {'aoi': geom_geojson}}, {'composite': {}}]
    tools_file = write_to_tmp_json_file(tools_json, 'tools.json')

    result = invoke([
        'create',
        '--name=test',
        '--id=4500474_2133707_2021-05-20_2419',
        '--bundle=analytic',
        '--item-type=PSOrthoTile',
        f'--tools={tools_file}'
    ])
    assert not result.exception

    order_request = {
        "name":
        "test",
        "products": [{
            "item_ids": ["4500474_2133707_2021-05-20_2419"],
            "item_type": "PSOrthoTile",
            "product_bundle": "analytic",
        }],
        "tools":
        tools_json
    }
    sent_request = json.loads(respx.calls.last.request.content)
    assert sent_request == order_request


def test_cli_orders_read_file_json_doesnotexist(invoke):
    result = invoke([
        'create',
        '--name=test',
        '--id=4500474_2133707_2021-05-20_2419',
        '--bundle=analytic',
        '--item-type=PSOrthoTile',
        '--tools=doesnnotexist.json'
    ])
    assert result.exception
    error_msg = ("Error: Invalid value for '--tools': 'doesnnotexist.json': " +
                 "No such file or directory")
    assert error_msg in result.output


def test_cli_orders_read_file_json_invalidjson(invoke, tmp_path):
    invalid_filename = tmp_path / 'invalid.json'
    with open(invalid_filename, 'w') as fp:
        fp.write('[Invali]d j*son')

    result = invoke([
        'create',
        '--name=test',
        '--id=4500474_2133707_2021-05-20_2419',
        '--bundle=analytic',
        '--item-type=PSOrthoTile',
        f'--tools={invalid_filename}'
    ])
    assert result.exception
    error_msg = "Error: File does not contain valid json."
    assert error_msg in result.output
