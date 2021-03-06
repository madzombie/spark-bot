"""A sample AWS Lambda function that can be used with a Cisco Spark Bot
for fetching information triggered by Spark messages.

A Spark Webhook can be created to trigger an HTTP POST to a targetUrl
such as an AWS API Gateway endpoint.

In this example, the Spark message id is extracted from the Webhook triggered POST to AWS (lambda_handler)

The examples use the Meraki Dashboard API, Spark API, and Tropo API.
 """

from __future__ import print_function

import json
import requests
import merakiapi
import meraki_info
import re
from prettytable import PrettyTable


my_api_key = meraki_info.api_key
bot_token = meraki_info.bot_token
my_org_id = meraki_info.org_id
my_net_id = meraki_info.net_id
spark_header = {
    'content-type': "application/json; charset=utf-8",
    'authorization': bot_token,
    'cache-control': "no-cache"
}
spark_url = 'https://api.ciscospark.com/v1/messages'
tropo_token = meraki_info.tropo_token
tropo_voice_token = meraki_info.tropo_voice_token
tropo_phone = meraki_info.tropo_phone
tropo_api_url = meraki_info.tropo_api_url
tropo_headers = {'accept': 'application/json',
                 'Content-Type': 'application/json'
                 }


def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }


# a function to get org inventory using the meraki dashboard api
# the json response is parsed and table rows are built
# the table is then posted by the bot to a Spark room
def spark_get_inventory_cmd(api_key, org_id, room_id):
    dashboard_response = merakiapi.getorginventory(api_key, org_id)
    table = PrettyTable(["Model", "Serial Number", "Mac Address"])
    for row in dashboard_response:
        dev_model = row['model']
        dev_serial = row['serial']
        dev_mac = row['mac']
        table_row = [dev_model, dev_serial, dev_mac]
        table.add_row(table_row)
    payload = {'roomId': str(room_id),
               'text': str(table)
               }
    bot_response_to_spark = requests.post(spark_url, data=json.dumps(payload), headers=spark_header)
    print(bot_response_to_spark.status_code)
    print(str(table))


# a function to get networks under an org (dashboard api)
# the json response is parsed and table rows are built
# the table is then posted by the bot to a Spark room
def spark_get_networks_cmd(api_key, org_id, room_id):
    dashboard_response = merakiapi.getnetworklist(api_key, org_id)
    table = PrettyTable(["Network ID", "Network Name", "Tags"])
    for row in dashboard_response:
        net_id = row['id']
        net_name = row['name']
        net_tags = row['tags']
        table_row = [net_id, net_name, net_tags]
        table.add_row(table_row)
    payload = {'roomId': str(room_id),
               'text': str(table.get_string(sortby="Network Name"))
               }
    bot_response_to_spark = requests.post(spark_url, data=json.dumps(payload), headers=spark_header)
    print(bot_response_to_spark.status_code)
    print(str(table.get_string(sortby="Network Name")))


# a function to get ssids under a network (dashboard api)
# the json response is parsed and table rows are built
# the table is then posted by the bot to a Spark room
def spark_get_ssids_cmd(api_key, net_id, room_id):
    dashboard_response = merakiapi.getssids(api_key, net_id)
    table = PrettyTable(["SSID #", "SSID Name", "Enabled?"])
    for row in dashboard_response:
        ssid_num = row['number']
        ssid_name = row['name']
        ssid_ena = row['enabled']
        table_row = [ssid_num, ssid_name, ssid_ena]
        table.add_row(table_row)
    payload = {'roomId': str(room_id),
               'text': str(table)
               }
    bot_response_to_spark = requests.post(spark_url, data=json.dumps(payload), headers=spark_header)
    print(bot_response_to_spark.status_code)
    print(table)


# Get network device inventory and create a list of MR's with the "guest" tag to a list
def get_guest_ap_list(api_key, net_id):
    """
    This function uses requests to GET a network's devices and creates a list of MR's
    with the 'guest_wireless' device tag
    """
    # creates the dictionary called net_devices to store key,value pairs
    serial_list = []
    result = merakiapi.getnetworkdevices(api_key, net_id)
    for row in result:
        if row == 'errors':
            return 'errors'
        else:
            # iterate through the json response from the GET inventory
            guest_regex = re.compile('guest_wireless')
            m = guest_regex.search(str(row['tags']))
            model = row['model']
            if model[:2] == 'MR' and m is not None:
                serial_list.append(row['serial'])
            else:
                continue
    return serial_list


# Get network device inventory and create a list of MR's
def get_ap_list(api_key, net_id):
    """
    This function uses requests to GET a network's devices and creates a list of MR's
    """
    # creates the dictionary called net_devices to store key,value pairs
    serial_list = []
    result = merakiapi.getnetworkdevices(api_key, net_id)
    for row in result:
        if row == 'errors':
            return 'errors'
        else:
            # iterate through the json response from the GET inventory
            model = row['model']
            if model[:2] == 'MR':
                serial_list.append(row['serial'])
            else:
                continue
    return serial_list


# Create a list of MR's with the "guest" tag and count clients on guest ip subnet
def spark_get_guest_clients_cmd(api_key, net_id, room_id):
    """ Creates a list of MR's with the 'guest_wireless' tag
    Counts clients on guest ip subnet
    """
    sn_list = get_guest_ap_list(api_key, net_id)
    client_count = 0
    table = PrettyTable(["Description", "IP", "MAC"])
    for sn in sn_list:
        result = merakiapi.getclients(my_api_key, sn, timestamp=900)
        for row in result:
            subnet_regex = re.compile('10.4.17')
            match = subnet_regex.search(str(row['ip']))
            if match is not None:
                client_count += 1
                client_name = row['description']
                client_ip = row['ip']
                client_mac = row['mac']
                table_row = [client_name, client_ip, client_mac]
                table.add_row(table_row)
            else:
                continue
    msg = "There are {0} users on the guest wireless network".format(str(client_count))
    payload = {'roomId': str(room_id),
                'text': str(msg)
                }
    payload2 = {'roomId': str(room_id),
                'text': str(table)
                }
    requests.post(spark_url, data=json.dumps(payload), headers=spark_header)
    requests.post(spark_url, data=json.dumps(payload2), headers=spark_header)


# Create a list of MR's and count clients on the guest ip subnet
def spark_get_mr_clients_cmd(api_key, net_id, room_id):
    """ Creates a list of MR's with the 'guest_wireless' tag
    Counts clients on guest ip subnet
    """
    sn_list = get_ap_list(api_key, net_id)
    client_count = 0
    mr_count = 0
    table = PrettyTable(["Description", "IP", "MAC"])
    for sn in sn_list:
        mr_count += 1
        result = merakiapi.getclients(my_api_key, sn, timestamp=900)
        for row in result:
            client_count += 1
            client_name = row['description']
            client_ip = row['ip']
            client_mac = row['mac']
            table_row = [client_name, client_ip, client_mac]
            table.add_row(table_row)
    msg = "There are {0} users on the wireless network across {1} MR devices".format(str(client_count),
                                                                                     str(mr_count))
    payload = {'roomId': str(room_id),
                'text': str(msg)
                }
    payload2 = {'roomId': str(room_id),
                'text': str(table)
                }
    requests.post(spark_url, data=json.dumps(payload), headers=spark_header)
    requests.post(spark_url, data=json.dumps(payload2), headers=spark_header)


# Create a list of MR's, clients and usage stats, then post the sorted results to the Spark room
def spark_get_top_talkers_cmd(api_key, net_id, room_id):
    client_traffic = {}
    sn_list = get_ap_list(api_key, net_id)
    table = PrettyTable(["Client", "Usage - kbytes past hour"])
    for sn in sn_list:
        result = merakiapi.getclients(api_key, sn, timestamp=3600)
        for row in result:
            traf_sum = row['usage']['sent'] + row['usage']['recv']
            description = row['description'].lower().replace(' ', '_').replace('.', '_')
            if description not in client_traffic:
                client_traffic[description] = traf_sum
            elif description in client_traffic:
                client_traffic[description] = client_traffic[description] + traf_sum
            else:
                continue
    for row in client_traffic:
        client_name = row
        client_usage = client_traffic[row]
        table_row = [client_name, client_usage]
        table.add_row(table_row)
        table.reversesort = True
    print(str(table.get_string(sortby="Usage - kbytes past hour")))
    payload = {'roomId': str(room_id),
                'text': str(table.get_string(sortby="Usage - kbytes past hour"))
                }
    requests.post(spark_url, data=json.dumps(payload), headers=spark_header)


# a simple error msg function
def spark_err_msg(room_id):
    bot_response = {'roomId': str(room_id),
                    'text': "Please enter a valid command"
                    }
    requests.post(spark_url, data=json.dumps(bot_response), headers=spark_header)
    print("Error, exiting...")

# example function sending json to a Tropo API endpoint
def meraki_rick_roll(number, room_id):
    # the data that will be passed in the POST to Tropo
    post_data = {"token": tropo_voice_token,
                 "number": number
                 }
    # tropo_data = post_data
    tropo_data = json.dumps(post_data)

    # issue the post and print the http response code and response
    tropo_post = requests.post(tropo_api_url, headers=tropo_headers, data=tropo_data)
    if tropo_post.status_code == 200:
        print(tropo_post.status_code)
        payload = {'roomId': str(room_id),
                   'text': "Success"
                   }
        requests.post(spark_url, data=json.dumps(payload), headers=spark_header)
    else:
        print(tropo_post.status_code)
        payload = {'roomId': str(room_id),
                    'text': "Something went wrong"
                    }
        requests.post(spark_url, data=json.dumps(payload), headers=spark_header)


# the lambda handler function
def lambda_handler(event, context):
    """Demonstrates a simple HTTP endpoint using API Gateway. You have full
    access to the request and response payload, including headers and
    status code.
    """
    # print the event details received from the Spark Webhook for logging
    print("Received event: " + json.dumps(event, indent=2))
    # assign the Spark message id to a variable
    msg_id = event['data']['id']
    # assign the Spark roomId to a variable (for the Bot to respond into the right room dynamically)
    room_id = event['data']['roomId']
    spark_msg_url = '{0}/{1}'.format(str(spark_url), str(msg_id))
    get_text = requests.get(spark_msg_url, headers=spark_header)
    t = json.loads(get_text.text)
    # t['text'] references "text":"<Spark message text>"
    # the following if statements parse the text of the Spark message and call
    # the appropriate functions based on the "command"
    if t['text'] == 'Meraki get ?':
        response = 'get [mr clients|guest clients|top talkers|inventory|networks|ssids]'
        payload = {'roomId': str(room_id),
                   'text': str(response)
                   }
        spark_response = requests.post(spark_url, data=json.dumps(payload), headers=spark_header)
        print(spark_response.status_code)

    elif t['text'] == 'Meraki get inventory':
        spark_get_inventory_cmd(my_api_key, my_org_id, room_id)

    elif t['text'] == 'Meraki get networks':
        spark_get_networks_cmd(my_api_key, my_org_id, room_id)

    elif t['text'] == 'Meraki get ssids':
        spark_get_ssids_cmd(my_api_key, my_net_id, room_id)

    elif t['text'] == 'Meraki get mr clients':
        spark_get_mr_clients_cmd(my_api_key, my_net_id, room_id)

    elif t['text'] == 'Meraki get guest clients':
        spark_get_guest_clients_cmd(my_api_key, my_net_id, room_id)

    elif t['text'] == 'Meraki get top talkers':
        spark_get_top_talkers_cmd(my_api_key, my_net_id, room_id)

    # there's always a Meraki easter egg
    elif str(t['text']).startswith("Meraki rick roll "):
        cmd_split = str(t['text']).split("Meraki rick roll ", 1)
        num_to_dial = cmd_split[1]
        if num_to_dial is not None:
            meraki_rick_roll(num_to_dial, room_id)
        else:
            spark_err_msg(room_id)

    # spark_create_network_cmd function to follow...
    # elif str(t['text']).startswith("Meraki create network "):
    #     cmd_split = str(t['text']).split("Meraki create network ", 1)
    #     net_name = cmd_split[1]
    #     if str(net_name) is not None:
    #         spark_create_network_cmd(my_api_key, my_org_id, net_name)
    #     else:
    #         spark_err_msg()
    else:
        spark_err_msg(room_id)

    return "Finished"
