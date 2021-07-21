import json
import os
import re
import yaml

ARCH='amd64'
HZN_ORG_ID='dev'
PROJECT='xibo'
INPUT_FILE='docker-compose.yml'

PROJECT_DIR='/tmp/' + PROJECT

def find_type(value):
    try:
        int(value)
        return "integer"
    except:
        pass
    
    try:
        float(value)
        return "float"
    except:
        pass
   
    if value.lower() == "true" or value.lower() == "false":
        return "boolean"
    else:
        return "string"
            
# x.y.z 1 or 1.0 or 1.0.1 allowed
def check_semver(version):
    semver_regex = re.compile(r'^\d+(\.\d+)?(\.\d+)?$')
    return re.match(semver_regex, version)

def gen_service(s_dict, s_org_id, s_name, s_arch):
    hzn_meta_dict = {}
    hzn_dict = {"MetadataVars" : hzn_meta_dict}
    service_dict = {}
    service_dict["org"] = s_org_id
    service_dict["label"] = s_name + "-" + s_arch
    service_dict["url"] = s_name
    service_dict["arch"] = s_arch
    service_dict["public"] = False
    service_dict["sharable"] = "singleton"

    hzn_meta_dict["SERVICE_NAME"] = s_name

    if 'mem_limit' in s_dict:
        print ("Ignoring... mem_limit: " + s_dict['mem_limit'])

    if 'restart' in s_dict:
        print ("Ignoring... restart: " + s_dict['restart'])

    req_services = []
    required_services = []
    service_dict["requiredServices"] = required_services
    if 'links' in s_dict:
        links = s_dict['links']
        for link in links:
            link_values = link.split(":") 
            if len(link_values) > 1:
                req_svc = {}
                req_svc["url"] = link_values[0]
                req_svc["org"] = s_org_id
                req_svc["version"] = "TBD"
                req_svc["versionRange"] = "TBD"
                req_svc["arch"] = s_arch
                required_services.append(req_svc)
                req_services.append(link_values[0])
                
    user_inputs = []
    service_dict["userInput"] = user_inputs
    if 'environment' in s_dict:
        envs = s_dict['environment']
        for env in envs:
            env_name_value = env.split("=") 
            if len(env_name_value) == 2:
                env_dict = {}
                env_dict["name"] = env_name_value[0]
                env_dict["defaultValue"] = env_name_value[1]
                env_dict["label"] = env_name_value[0].lower()
                env_dict["type"] = find_type(env_name_value[1])
                user_inputs.append(env_dict)
            else:
                print ("Error: Not enough value. Skipping " + env)
    
    if 'image' in s_dict:
        image_str = s_dict['image']
        image_name_version = image_str.split(":") 
        if len(image_name_version) == 2:
            if check_semver(image_name_version[1]):
                service_dict["version"] = image_name_version[1]

                deployment_dict= {}
                services_dict = {}
                service_name_dict = {}
                service_details_dict = {}

                service_dict["deployment"] = deployment_dict
                deployment_dict["services"] = service_name_dict
                service_name_dict[s_name] = service_details_dict
                service_details_dict["image"] = image_name_version[0] + ":" + image_name_version[1]

                if 'volumes' in s_dict:
                    service_binds = []
                    service_details_dict["binds"] = service_binds
                    volumes = s_dict['volumes']
                    for volume in volumes:
                        service_binds.append(volume)
                        
                if 'ports' in s_dict:
                    service_ports = []
                    service_details_dict["ports"] = service_ports
                    ports = s_dict['ports']
                    for port in ports:
                        port_dict = {}
                        port_dict["HostPort"] = port + ":tcp"
                        port_dict["HostIP"] = "0.0.0.0"
                        service_ports.append(port_dict)
                        
                hzn_meta_dict["IMAGE_NAME"] = image_name_version[0]
                hzn_meta_dict["SERVICE_VERSION"] = image_name_version[1]
            else:
                print ("Error: Image version not supported " + image_name_version[1]) 
                print ("       Must have a version number in the format x.y.z e.g:  1 or 1.0 or 1.2.3") 
                print ("       Re-tag the image with suggested version format and use that") 
        else:
            print ("Error: not enough expressions in " + image_str) 
            print ("       Must have a version number in the format x.y.z e.g:  1 or 1.0 or 1.2.3") 
        
    gen_service = {}
    gen_service["hzn"] = hzn_meta_dict
    gen_service["service"] = service_dict

    return gen_service, req_services

if __name__ == '__main__':
    with open(INPUT_FILE) as f:

        data = yaml.load(f, Loader=yaml.FullLoader)
        print(data)
        print("\n")
              
        if 'services' in data:
            if not os.path.exists(PROJECT_DIR):
                os.mkdir(PROJECT_DIR)

            services_dict = {}
            services_dict["services"] = {}
            services_dict["req_services"] = []
            for service in data['services']:
                service_dict = data['services'][service]
                gen_service_dict, req_services = gen_service(service_dict, HZN_ORG_ID, service, ARCH)
                services_dict["services"][service] = gen_service_dict
                if len(req_services) > 1:
                    services_dict["req_services"].append(req_services) 

            for req_services in services_dict["req_services"]:
                for req_service in req_services:
                    service_dict = services_dict["services"][req_service]
                    for service in services_dict["services"]:
                        for requiredService in services_dict["services"][service]["service"]["requiredServices"]:
                            if requiredService["url"] == req_service:
                                requiredService["version"] = service_dict["service"]["version"]
                
            for service in services_dict["services"]:
                service_dir = PROJECT_DIR + "/" + service

                if not os.path.exists(service_dir):
                    os.mkdir(service_dir)

                with open(service_dir + "/hzn.json", 'w') as f:
                    print(json.dumps(services_dict["services"][service]["hzn"]), file=f)
    
                with open(service_dir + "/service.definition.json", 'w') as f:
                    print(json.dumps(services_dict["services"][service]["service"]), file=f)
            
