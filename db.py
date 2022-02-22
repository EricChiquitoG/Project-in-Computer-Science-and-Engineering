from ctypes import string_at
import re
from string import Template
from unicodedata import name
from bson.json_util import object_hook
from pymongo import MongoClient
from datetime import datetime
from werkzeug import datastructures
from werkzeug.security import generate_password_hash
import uuid
import hashlib
from user import User
import json
from bson import ObjectId


## Change this to your mongodb cluster (in case you want to use it) for you to see and modify the database
client = MongoClient("mongodb+srv://EricTest:test@cluster0.ozw3z.mongodb.net/myFirstDatabase?retryWrites=true&w=majority", ssl=True,ssl_cert_reqs='CERT_NONE')

# This will allow you to access the databases, in case more databases are needed add them here, no need to create a struture a priori like SQL,
# when data is added to a non existing database it will create it.

nego2 = client.get_database("Nego2")
users_collection = nego2.get_collection("users")
access_collection =nego2.get_collection("access_permissions")
negotiations_collection= nego2.get_collection("negotiations")
templates_collection=nego2.get_collection("templates")
contracts_collection=nego2.get_collection("contracts")
## Write how to specify regarding the access giving permisions
data_collection=nego2.get_collection("datasets")


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId) or isinstance(o, datetime):
            return str(o)
        return json.JSONEncoder.default(self, o)


## Run this function when you want to create a new user, you can also create a registration view in the api which call this function, is up to you.
def save_user(username, email, password,sign):
    password_hash = generate_password_hash(password)
    salt = uuid.uuid4().hex
    hashsign = hashlib.sha256(salt.encode() + sign.encode()).hexdigest() + ':' + salt
    user_id=users_collection.insert_one({'username': username, 'email': email, 'password': password_hash,'sign':hashsign})
    return user_id


## In case you want to create aditional templates you would need to modify and run this function.
def add_template1():
    temp_type='parent_contract'
    temp="This contract $contract_name for data access with contract_id $contract_id is entered between the group $group hereinafter refered to as buyer, and $supplier hereinafter refered as supplier. The supplier agrees to provide the buyer group and all the members contained on it for a maximum of $user_ammount users, with access to the data resource(s) $data_resources in accordance with the following terms: The requested buyer shall have access to the requested resource(s) $data_resources with access rights $access_rights. From $st_date to $end_date after which moment the access permissions will be removed. Buyer signature $buyer_sign. Supplier signature $seller_sign"
    templates_collection.insert_one({'temp_type':temp_type,'template':temp})
def add_template():
    temp_type='child_contract'
    temp="This sub-contract for data access with contract_id $contract_id which refers to the parent_contract {LTU-Boliden}, with id $contract_id, is entered between the user $user and manager $man. The user agrees to be part of the work group $group for the following $data_resources with access rights $access_rights. The child agrees to give proper use, not share nor distribute the data which is granted access according to General Data protection regulation GDPR.  Access to the data is granted from $st_date to $end_date at which point rights will be revoked. User signature $buyer_sign. Manager signature $seller_sign"
    templates_collection.insert_one({'temp_type':temp_type,'template':temp})

# Gets the user data, used for the login system
def get_user(username):
    user_data = users_collection.find_one({'username': username})
    return User(user_data['username'], user_data['email'], user_data['password'],user_data['sign']) if user_data else None

# Creates a new permission request and creates the first offer of the negotiation
def parent(neg_type,username, user_ammount,item, st_date, end_date, role,offering):
    status= 'submitted'
    contract_name=neg_name_gen(username,item)
    access_req=access_collection.insert_one(
                {'type':neg_type,'contract_name':contract_name,'demander':username, 'provider':get_provider(item), 'creation_date':datetime.now(),'offer': offering,'request_details':
                                                                                                        {'user_ammount':user_ammount,'item':item,'start_date':st_date,'end_date':end_date,'role':role},'status':status }).inserted_id
        ## Add new nego
    offer_parent(access_req,username,user_ammount, item, st_date, end_date, role,offering)
    return access_req


def child(neg_type,parent_id,parent_name,username,item, st_date, end_date, role,offering): #Child agreement need parent agreement name i.e. LTU- Boliden to create children agreement
    status= 'submitted'
    parent_data=parent_info(parent_name)
    access_req=access_collection.insert_one(
                {'type':neg_type,'parent_id':parent_id,'parent_name':parent_name,'demander':username, 'provider':parent_data['demander'], 'creation_date':datetime.now(),'offer': offering,'request_details':
                                                                                                        {'item':item,'start_date':st_date,'end_date':end_date,'role':role},'status':status }).inserted_id
    ## Add new nego
    offer_child(access_req,username,1, item, st_date, end_date, role,offering,parent_data['demander'])
    return access_req

# Function that creates orders for parent and children agreements
def offer_parent(req_id,username, user_ammount,item, st_date, end_date, role,offering):
    dataset=data_collection.find_one({'name':item})
    negotiations_collection.insert_one({'req_id':ObjectId(req_id),'demander':username, 'provider':get_provider(item), 'creation_date':datetime.now(),'offer': offering ,'request_details':
                                                                                                        {'user_ammount':user_ammount,'item_id': dataset['_id'], 'item':item,'start_date':st_date,'end_date':end_date,'role':role}})
def offer_child(req_id,username, user_ammount,item, st_date, end_date, role,offering,demander):
    dataset=data_collection.find_one({'name':item})
    negotiations_collection.insert_one({'req_id':ObjectId(req_id),'demander':username, 'provider':demander, 'creation_date':datetime.now(),'offer': offering ,'request_details':
                                                                                                        {'user_ammount':user_ammount,'item_id': dataset['_id'], 'item':item,'start_date':st_date,'end_date':end_date,'role':role}})

# This will get the provider of the specified resource name
def get_provider(name ):
    dataset=data_collection.find_one({'name':name})
    owner=dataset['owner']
    print(owner)
    return owner

# changes the status of the access permission depending on what is sent and who sends it.
def change_status(req_id, flag,user):
    #The hard coded posibilities is the acceptance and rejection
    access_request=get_neg(req_id)
    if flag=='accept':
        access_collection.update_one({'_id':ObjectId(req_id)}, {'$set':{'status':'accepted'}})
        print('accepted')
    elif flag=='reject':
        access_collection.update_one({'_id':ObjectId(req_id)}, {'$set':{'status':'rejected'}})
        print('rejected')
    else:
        if user==get_provider(access_request['request_details']['item']):
            access_collection.update_one({'_id':ObjectId(req_id)}, {'$set':{'status':'counter_offer'}})
            print('counter offer')
        else:
            access_collection.update_one({'_id':ObjectId(req_id)}, {'$set':{'status':'offer'}})
            print('new offer')
    return('finished')

# This is used to add new datasets to the database
def new_dataset(name, owner, read, modify, delete):
    data_collection.insert_one({'name':name,'owner': owner, 'permissions': {'read':read, 'modify':modify, 'delete':delete}})

# Gets the access permission data based on the id
def get_neg(req_id):
    neg= access_collection.find_one({'_id':ObjectId(req_id)})
    return neg

# Gets the template based on the name
def get_template(temp_type):
    temp_id=templates_collection.find_one({'temp_type':temp_type})
    return temp_id['template']

# Get the signature of the user by its username
def get_sign(uid):
    user_info=users_collection.find_one({'username':uid})
    return user_info['sign']

# Updates the access permission
def update(req_id, offer, item, start_date, end_date, role):
    access_collection.update({'_id':ObjectId(req_id)},{'$set': {'offer':offer, 
                                                                'request_details.item':item,
                                                                'request_details.start_date':start_date,
                                                                'request_details.end_date':end_date,
                                                                'request_details.role':role}})

# Signs the contract and returns it 
def sign_contract(req_id,type):
    neg= access_collection.find_one({'_id':ObjectId(req_id)})

    if type=='parent':

        temp_type= "parent_contract" # Sign contract for Parent
        temp=Template(get_template(temp_type))
        d= dict(contract_name=neg['contract_name'],contract_id=neg['_id'],supplier=neg['provider'],group=neg['demander'],user_ammount=neg['request_details']['user_ammount'],data_resources=neg['request_details']['item'],st_date=neg['request_details']['start_date'],end_date=neg['request_details']['end_date'],
        access_rights=neg['request_details']['role'],seller_sign=get_sign(neg['provider']), buyer_sign=get_sign(neg['demander']) )
    elif type=='child':
        
        temp_type= "child_contract" # Sign contract for child
        temp=Template(get_template(temp_type))
        d= dict(contract_id=neg['_id'],parent_name=neg['parent_name'],parent_id=neg['parent_id'],man=neg['provider'],user=neg['demander'],group=neg['parent_name'],data_resources=neg['request_details']['item'],st_date=neg['request_details']['start_date'],end_date=neg['request_details']['end_date'],
        access_rights=neg['request_details']['role'],seller_sign=get_sign(neg['provider']), buyer_sign=get_sign(neg['demander']) )
    signed_c=temp.safe_substitute(d)
    contracts_collection.insert_one({'req_id':ObjectId(req_id), 'provider':neg['provider'],'demander':neg['demander'],'creation_date': datetime.now(),'contract':signed_c})
    return signed_c

#Return all the finished negotiations available for the current user
def negotiations(user):
    negotiations= list(access_collection.find({'type':'parent','status':'accepted',"provider":{"$ne":user}}))
    keys_to_remove=['type','offer','status']
    for i in negotiations:
        for j in keys_to_remove:
            i.pop(j)
    return(JSONEncoder().encode(negotiations))

#Find resources to negotiatiate on, can only negotiate in parent negotiations
def find_resources(user): 
    data_resources=list(data_collection.find({"owner":{"$ne":user}}))
    return(JSONEncoder().encode(data_resources))

#Checks if the parent agreement exists and if it has already concluded
def parent_acc_check(parent):
    parent= access_collection.find_one({'_id':ObjectId(parent)})
    if parent['status']=='accepted':
        return 'Parent accepted'
    else: False

#Checks if the date of the child agreement is between the ranges specified in parent contract
def date_check(parent,st_date,end_date):
    parentagg= access_collection.find_one({'_id':ObjectId(parent)})
    if parentagg['request_details']['start_date']>st_date or parentagg['request_details']['end_date']<end_date:
        return False
    else:
        return 'date check passed'

#Generates the name of the agreement in parent contracts between group and database owner i.e. LTU and Boliden returns LTU - Boliden
def neg_name_gen(group, data_source):
    sup=get_provider(data_source)
    agg_name=group+' - '+sup
    print(agg_name)
    return agg_name

#Returns information of the parent contract
def parent_info(name):
    neg=access_collection.find_one({'contract_name':name})
    return(neg)

