#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##
# Copyright 2023 FIWARE Foundation, e.V.
#
# Adapted from IoTAgent-SDMX (RDF Turtle) by Franc Drobnič
#
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#

from pathlib import Path
import json
from requests import post, exceptions
from fastapi import status
from sdmx2jsonld.transform.parser import Parser
from io import StringIO
from logging import getLogger


class NGSILDConnector:
    def __init__(self, path=None):
        self.logger = getLogger(__name__)
        if path is None:
            config_path = Path.cwd().joinpath("common/config.json")
        else:
            config_path = Path.cwd().joinpath(path)

        with open(config_path) as config_file:
            config = json.load(config_file)

        self.base_url = config["broker"]

    def get_url(self):
        url = f"{self.base_url}/ngsi-ld/v1/entities"
        return url

    def send_data_array(self, json_object):
        return_info = []
        d = json.loads(json_object)
        d = d if type(d) is list else [d]

        for elem in d:
            try:
                rc, r = self.send_data(json.dumps(elem, indent=4))
                return_info.append({"id": elem["id"], "status_code": rc, "reason": r})
            except TypeError as e:
                return_info.append(
                    {
                        "id": "UNK",
                        "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                        "reason": e.args[0],
                    }
                )
            except Exception as e:
                raise e
                # reason = getattr(e, 'message', str(e))
                # return_info.append({"id": "UNK",
                #                     "status_code": 500,
                #                    "reason": reason})

        return return_info

    def send_data(self, json_object):
        # Send the data to a FIWARE Context Broker instance
        headers = {
            "Content-Type": "application/ld+json"
            # , 'Accept': 'application/ld+json'
        }

        url = self.get_url()
        resp = "..."

        response = post(url=url, headers=headers, data=json_object, timeout=5)

        # resp = json.loads(r.text)
        response_status_code = response.status_code

        if response_status_code == status.HTTP_201_CREATED:
            self.logger.debug(f"LOCATION: {response.headers['Location']}")
        if response_status_code == status.HTTP_400_BAD_REQUEST:
            self.logger.info(f" Parser error: {response.reason}\n{json_object}")

        # Let exceptions raise.... They can be controlled somewhere else.
        return response_status_code, response.reason


if __name__ == "__main__":
    c = NGSILDConnector("../common/config.json")
    print(c.get_url())

    with open("../sdm/dataModel.ACDSi/ACDSiMeasurement/example-normalized.jsonld", "r") as rf:
    #with open("../sdm/dataModel.S4BLDG/Actuator/example-normalized.jsonld", "r") as rf:
        r = rf.read()

    s = c.send_data_array(r)
    print(s)
