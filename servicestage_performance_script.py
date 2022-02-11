import sys
import random
import time
import requests
import json
import urllib3
urllib3.disable_warnings()

def post(url=None, headers=None, body=None):
    if 'iam' in url:
        return requests.post(url, headers=headers, data=body, timeout=30, verify=False)
    else:
        resp = requests.post(url, headers=headers, data=body, timeout=30, verify=False)
        if 200 <= resp.status_code < 300:
            return resp.json()
        else:
            print(url, resp.content)

def get(url=None, headers=None, queries=None, timeout=10):
    resp = requests.get(url, headers=headers, params=queries, verify=False, timeout=timeout)
    if 200 <= resp.status_code < 300:
        return resp.json()
    else:
        print(url, resp.content)

def delete(url=None, headers=None, body=None):
    print("start exec delete request {}".format(url))
    return requests.delete(url, headers=headers, data=body, verify=False)

def get_user_token(iam_endpoint=None, domain_name=None, user_name=None, project_name=None, pwd=None):
    scope = {"project": {"name": project_name}}
    if not project_name:
        scope = {"domain": {"name": domain_name}}
    if not user_name:
        user_name = domain_name
    body = {"auth": {"identity": {"methods": ["password"], "password": {
        "user": {"domain": {"name": domain_name}, "name": user_name, "password": pwd}}}, "scope": scope}}
    headers = {"Content-Type": "application/json"}
    url = "%s/v3/auth/tokens" % iam_endpoint
    return post(url=url, headers=headers, body=json.dumps(body))

class ServiceStage:
    def __init__(self, address, user_token, projectid):
        self.__address = address
        self.__user_token = user_token
        self.__projectid = projectid
        self.__headers = {'Content-Type': 'application/json', "x-auth-token": self.__user_token,}

    def get_environment(self):
        url = "%s/v2/%s/cas/environments" % (self.__address, self.__projectid)
        return get(url=url, headers=self.__headers)

    def create_application(self, app_name):
        url = "%s/v2/%s/cas/applications" % (self.__address, self.__projectid)
        body = {"name": app_name, "description": ""}
        return post(url=url, headers=self.__headers, body=json.dumps(body))

    def get_application(self):
        url = "%s/v2/%s/cas/applications" % (self.__address, self.__projectid)
        return get(url=url, headers=self.__headers)

    def delete_application(self, application_id):
        url = "%s/v2/%s/cas/applications/%s" % (self.__address, self.__projectid, application_id)
        return delete(url=url, headers=self.__headers)

    def create_component(self, application_id, component_name, runtime, category, sub_category=None):
        url = "%s/v2/%s/cas/applications/%s/components" % (self.__address, self.__projectid, application_id)
        body = {"name": component_name, "runtime": runtime, "category": category, "sub_category": sub_category}
        return post(url=url, headers=self.__headers, body=json.dumps(body))

    def get_component(self, application_id):
        url = "%s/v2/%s/cas/applications/%s/components/overviews" % (self.__address, self.__projectid, application_id)
        return get(url=url, headers=self.__headers)

    def delete_component(self, application_id, component_id):
        url = "%s/v2/%s/cas/applications/%s/components/%s?force=true" % (self.__address, self.__projectid, application_id, component_id)
        return delete(url=url, headers=self.__headers)

    def delete_instance(self,application_id, component_id, instance_id):
        url = "%s/v2/%s/cas/applications/%s/components/%s/instances/%s" % (self.__address, self.__projectid, application_id, component_id, instance_id)
        return delete(url, self.__headers)

    def create_instance(self, application_id, component_id, env_id, cluster_id,cluster_type,component_name,image_url,engine_id=None):
        instance_name = "%s-inst-%s" % (component_name,random.randint(100000, 999999))
        url = "%s/v2/%s/cas/applications/%s/components/%s/instances" % (self.__address, self.__projectid, application_id, component_id)
        refer_resources = [{"id": cluster_id, "type": "cce", "parameters": {"type": cluster_type, "namespace": "default"}}]
        if engine_id:
            cse_resources={"id": engine_id, "type": "cse"}
            refer_resources.append(cse_resources)
        artifacts = {component_name: {"storage": "swr", "type": "image", "url": image_url, "auth": "iam", "version": "1.0.0", "properties": {}}}
        body = {"name": instance_name, "version": "1.0.0", "environment_id": env_id,
                "flavor_id": "CUSTOM-10G:null-null:null-null", "replica": 2, "artifacts": artifacts,
                "refer_resources": refer_resources}
        return post(url=url, headers=self.__headers, body=json.dumps(body))

    def get_instance_status(self, application_id, component_id, instance_id):
        url = "%s/v2/%s/cas/applications/%s/components/%s/instances/%s" % (self.__address, self.__projectid, application_id, component_id, instance_id)
        for i in range(20):
            res = get(url, self.__headers)
            status = res['status_detail']['status']
            if status == 'INITIALIZING':
                print('Instance deploying...')
                time.sleep(30)
            else:
                break

def main():
    if sys.version_info.major == 2:
        from ConfigParser import ConfigParser
        config = ConfigParser()
        config.read("servicestage_param")
    else:
        from configparser import ConfigParser
        config = ConfigParser()
        config.read('servicestage_param', encoding='utf-8')
    cfg = config._sections["servicestage"]
    iam_endpoint = cfg.get('iam_endpoint')
    domain_name = cfg.get('domain_name')
    user_name = cfg.get('user_name')
    project_name = cfg.get('project_name')
    pwd = cfg.get('password')
    servicestage_endpoint = cfg.get('servicestage_endpoint')
    cluster_type=cfg.get('cluster_type')
    resp = get_user_token(iam_endpoint=iam_endpoint, domain_name=domain_name, user_name=user_name,
                          project_name=project_name, pwd=pwd)
    user_token = resp.headers.get("x-subject-token")
    project_id = json.loads(resp.content)["token"]["project"]["id"]
    servicestage = ServiceStage(servicestage_endpoint, user_token, project_id)
    environment_list=servicestage.get_environment()
    env_id=environment_list['environments'][0]['id']
    for base_resources in environment_list['environments'][0]['base_resources']:
        if base_resources['type'] == 'cce':
            cluster_id = base_resources['id']
            break
    for optional_resources in environment_list['environments'][0]['optional_resources']:
        if optional_resources['type'] == 'cse':
            cse_id = optional_resources['id']
            break
    if cfg.get('performance_type') == "cse":
        app_name="app-performance-test-%s" % random.randint(1000, 9999)
        app_res=servicestage.create_application(app_name)
        app_id=app_res['id']
        image_url=cfg.get('cse_image_url')
        for i in range(50):
            component_name="comp-test-%s" % random.randint(1000, 9999)
            comp_res=servicestage.create_component(app_id, component_name, "Docker", "MicroService", sub_category="Java Chassis")
            comp_id=comp_res['id']
            comp_name=comp_res['name']
            inst_res=servicestage.create_instance(app_id, comp_id, env_id, cluster_id, cluster_type,comp_name, image_url, engine_id=cse_id)
            inst_id=inst_res['instance_id']
            servicestage.get_instance_status(app_id, comp_id, inst_id)
            time.sleep(1)
    elif cfg.get('performance_type') == "app":
        app_name="app-performance-test-%s" % random.randint(1000, 9999)
        app_res=servicestage.create_application(app_name)
        app_id=app_res['id']
        image_url = cfg.get('app_image_url')
        for i in range(1000):
            component_name="comp-test-%s" % random.randint(1000, 9999)
            comp_res=servicestage.create_component(app_id, component_name, "Docker", "Webapp", sub_category="Web")
            comp_id=comp_res['id']
            comp_name=comp_res['name']
            inst_res=servicestage.create_instance(app_id, comp_id, env_id, cluster_id, cluster_type, comp_name, image_url)
            inst_id=inst_res['instance_id']
            servicestage.get_instance_status(app_id, comp_id, inst_id)
            time.sleep(1)
    elif cfg.get('performance_type') == "clean":
        app_list = servicestage.get_application()
        for app_info in app_list['applications']:
            app_id = app_info['id']
            comp_list = servicestage.get_component(app_id)
            if comp_list['components']:
                for comp_info in comp_list['components']:
                    comp_id = comp_info['id']
                    servicestage.delete_component(app_id, comp_id)
            for i in range(10):
                comp_list = servicestage.get_component(app_id)
                if comp_list['count'] == 0:
                    servicestage.delete_application(app_id)
                    break
                else:
                    time.sleep(30)
    else:
        print("performance_type key's error")

if __name__ == '__main__':
    main()
