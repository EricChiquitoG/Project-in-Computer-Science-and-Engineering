from datetime import datetime
from re import S

from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_cors import CORS



from db import child, date_check, find_resources, get_provider, get_user, get_neg, neg_name_gen, change_status, negotiations, offer_parent, parent, parent_acc_check, parent_info, sign_contract, update

app = Flask(__name__)

cors = CORS(app)
app.secret_key = "sfdjkafnk"
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


#User login receives form params username and password

@app.route('/login', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return {"message":"The user {} is already authenticated".format(current_user.username)},200

    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password_input = request.form.get('password')
        user = get_user(username)

        if user and user.check_password(password_input):
            login_user(user)
           
            return {"message":"User {} has been authenticated".format(str(current_user.username))},200
        else:
            message = 'Failed to login!'
    return message,400

# User logout

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return {'message':'the user has logged out'},200



# Start negotiation: 

@app.route("/negotiate/parent", methods=['POST']) #Starts a negotiation for parent contract
@login_required
def parent_neg():
    try: 
        item=request.form.get('item')
        nag_type='parent'
        st_date=request.form.get('st_date')
        end_date=request.form.get('end_date')
        role=request.form.get('role')
        offering=request.form.get('offering')
        user=current_user.username
        print(current_user.username)
        user_amm=request.form.get('user_ammount')
        #The following function may be changed to iterate if multiple roles are requested
        
        #neg_id=new_permi(current_user.username, item, st_date, end_date, role,offering)

        neg_id =parent(nag_type,user,user_amm,item,st_date,end_date,role,offering)
    
        print(neg_id)
        return {"message":"The negotiation with id {} has been created".format(str(neg_id))},200
    except Exception as e: print(e)

@app.route("/negotiate/child", methods=['POST']) #Starts negotiation for child, needs parent contract
@login_required
def child_neg():
    try: 
        item=request.form.get('item')
        nag_type='child'
        st_date=request.form.get('st_date')
        end_date=request.form.get('end_date')
        role=request.form.get('role')
        offering=request.form.get('offering')
        user=current_user.username
        #The following function may be changed to iterate if multiple roles are requested
        parent_name=request.form.get('parent_name')
        parent_contract=parent_info(parent_name)
        if parent_acc_check(parent_contract['_id']):
            print('Parent contract ok')
        else:
            return {"message":"The negotiation hasnt ended or does not exist"},403
        if date_check(parent_contract['_id'],st_date,end_date):
            print("date format ok")
        else:
            return {"message":"The requested dates does not match with parent contract date frames"},403
        neg_id=child(nag_type,parent_contract['_id'],parent_name,user,item,st_date,end_date,role,offering)
        print(neg_id)
        return {"message":"The negotiation with id {} has been created".format(str(neg_id))},200
    except Exception as e: print(e)

# Negotiation or back and forth of proposals: (only for parents)
# To be done: Verify that new proposal is different to the previous one and that the porposer is different than the one who proposed the last

@app.route("/negotiate/<req_id>", methods=['GET','POST'])
@login_required
def neg(req_id):
    req=get_neg(req_id)
    print(req)
    if request.method == 'POST':
        if req['type']=='parent':
            if current_user.username in (req['provider'],req['demander']):
                if req['status'] not in ('accepted', 'rejected'):
                    item=request.form.get('item')
                    st_date=request.form.get('st_date')
                    end_date=request.form.get('end_date')
                    role=request.form.get('role')
                    offering=request.form.get('offering')
                    user_amm=request.form.get('user_ammount')
                    offer_parent(ObjectId(req_id), current_user.username,user_amm, item, st_date, end_date, role,offering)
                    update(req_id,offering,item,st_date,end_date,role)
                    change_status(req_id,1,current_user.username)
                    return  {"message":"New offer submited for request with id {}".format(str(req['_id']))},200
                else:
                    return  {"message":"The negotiation {} has concluded no more offers can be made".format(str(req['_id']))},403
            else:
                return{"message":'You are not part of the current negotiation'}, 403
        else: 
            return  {"message":"Cannot bid on child negotiation {}".format(str(req['_id']))},403

# Only accesible to the owner of such resource, this route accepts the negotiation and begins the contract signing
@app.route("/negotiate/<req_id>/accept", methods=['GET'])
@login_required
def accept(req_id):
    req=get_neg(req_id)
    if current_user.username == req['provider']:
        change_status(req_id, 'accept',current_user.username)
        s=sign_contract(req_id,req['type'])
        print(s)
        ## Add function for contract writing
        return  {"message":"The negotiation with id {} has been accepted.".format(str(req['_id'])), "Contract": "{}".format(s)},200

    else: return {"message":'You are not authorized to perform this task'},403



# Only accesible to the owner of such resource, this route cancels the negotiation.
@app.route("/negotiate/<req_id>/cancel", methods=['GET'])
@login_required
def cancel(req_id):
    req=get_neg(req_id)
    if current_user.username == req['provider']:
        change_status(req, 'reject')
        return  {"message":"The negotiation with id {} has been reject".format(str(req['_id']))},200

    else: return {"message":'You are not authorized to perform this task'},403 


#This route shows the data resources available to negotiate in
@app.route("/negotiate/resources", methods=['GET'])
@login_required
def resources():
    available_data=find_resources(current_user.username)
    return available_data

#This route show the available data that users can negotiate on existing parents
@app.route("/negotiate/providers", methods=['GET'])
@login_required
def providers():
    available_data=negotiations(current_user.username)
    return available_data

@login_manager.user_loader
def load_user(username):
    return get_user(username)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
