from flask import Flask, render_template, request
import sys
import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.header import Header
from email import encoders


import re;
import imaplib
import email
from email.header import decode_header
import webbrowser
import os

import sqlite3
from sqlite3 import Error


def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)

def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file,check_same_thread=False)
        return conn
    except Error as e: pass;
    return conn

# Database
database = r"data.db"
conn = create_connection(database)

def create_table(create_table_sql):
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        conn.commit()
    except Error as e:
        pass;


def add_vals(mails):
    try:
        sql = ''' INSERT INTO mails(id, sender, receiver, subject, body)
                  VALUES(?,?,?,?,?)'''
        
        cur = conn.cursor()
        cur.execute(sql,mails)
        conn.commit()
    except Exception as e: pass;

def create_all_folders_db(folders):
        sql_check_table_exists = """SELECT count(*) FROM sqlite_master 
                                    WHERE type='table' AND name='folders';"""

        cur = conn.cursor();
        cur.execute(sql_check_table_exists);
        if cur.fetchall()[0][0]: return;

        sql_create_folder = """ CREATE TABLE folders (
                                        id integer PRIMARY KEY AUTOINCREMENT,
                                        name text NOT NULL UNIQUE,
                                        def boolean NOT NULL
                                    ); """

        sql_create_folder_link = """ CREATE TABLE folders_link (
                                        id integer PRIMARY KEY AUTOINCREMENT,
                                        mail_id integer NOT NULL,
                                        folder_id integer NOT NULL,
                                        FOREIGN KEY (mail_id) REFERENCES mails (id), 
                                        FOREIGN KEY (folder_id) REFERENCES folders (id), 
                                        CONSTRAINT folder_link_constraint UNIQUE (mail_id, folder_id)
                                ); """

        sql_create_sent_mails = """ CREATE TABLE sent_mails (
                                        id integer PRIMARY KEY,
                                        sender text NOT NULL,
                                        receiver text NOT NULL,
                                        subject text,
                                        body text
                                ); """

        if conn is not None:
            create_table(sql_create_folder);
            create_table(sql_create_folder_link);
            create_table(sql_create_sent_mails);
            for folder in folders.keys():
                insert_folder_db(folder, 1);
        else:
            print("Error! cannot create the database connection.");

def retrieve_custom_folders_db() -> dict:
    cur = conn.cursor()
    cur.execute("SELECT * FROM folders WHERE folders.def == 0");
    cf = {};
    for folders in cur.fetchall(): cf[folders[1]] = (Folder(folders[1]), 0);
    return cf;

def insert_folder_db(name, default) -> bool:
    try:
        cur = conn.cursor()
        cur.execute('''INSERT INTO folders(name, def) VALUES(?,?)''', (name, default,))
        conn.commit()
        return 1;
    except Exception as e:
        return 0;

def delete_folder_db(name) -> bool:
    try:
        cur = conn.cursor()
        cur.execute('''DELETE FROM folders WHERE folders.name == (?)''', (name,))
        conn.commit()
        return 1;
    except Exception as e:
        return 0;

def insert_sent_mails_db(mails) -> bool:
    try:
        sql = ''' INSERT INTO sent_mails(id, sender, receiver, subject, body)
                  VALUES(?,?,?,?,?)'''
        
        cur = conn.cursor()
        cur.execute(sql, mails)
        conn.commit()
    except Exception as e: pass;

app = Flask(__name__)

# Current User
username = "ooadlab1@gmail.com"
password = "ooadlab1teami6"

# Authenticate
imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(username, password)

drafts = {}

class Mail:
    def __init__(self, id, sender, receiver, subject, body):
        self.id = id;
        self.sender = sender
        self.receiver = receiver.strip()
        self.subject = subject.strip()
        self.body = body.strip()


class MailBox:
    def __init__(self):
        self.folders = {"Sent" : (Sent(), 1), "Important" : (Important(), 1), "Spam" : (Spam(), 1), "Trash" : (Trash(), 1), "Archive" : (Archive(), 1)};
        create_all_folders_db(self.folders);
        self.folders.update(retrieve_custom_folders_db()); 
    
    def compose(self, receivers, subject, body):
        file_name = ""
        mail_id = len(self.folders["Sent"][0].mails)+1;
        compose_mail = Draft(self.folders["Sent"][0], receivers, body, file_name, subject, mail_id)
        drafts[mail_id] = compose_mail
        return compose_mail
    
    def create_folder(self, name):
        if name not in self.folders:
            self.folders[name] = (Folder(name),0)
            insert_folder_db(name, 0);
            print("Folder Created")
        else:
            print("Folder Already Exists")
    
    def delete_folder(self, name):
        if name in self.folders:
            print(self.folders[name])
            if not self.folders[name][1]:
                delete_folder_db(name);
                self.folders.pop(name);
                print("Folder Deleted")
            else:
                print("Folder Marked Default")
        else:
            print("Folder Doesnt Exists")

    def show(self, name):
        try:
            if name not in self.folders.keys(): return 0;
            cur = conn.cursor()
            cur.execute('''SELECT id FROM folders WHERE folders.name == (?)''', (name,));
            cur.execute('''SELECT mail_id FROM folders_link WHERE folder_id == (?)''', (cur.fetchall()[0][0],))
            mails = [];
            for mail_id in cur.fetchall():
                cur.execute('''SELECT * FROM mails WHERE id == (?)''', (mail_id[0],));
                mail = cur.fetchall()[0];
                mails.append(Mail(mail[0], mail[1], mail[2], mail[3], mail[4]));
            return mails;
        except Exception as e:
            return 0;
    
    def delete(self, mailid):
        self.send_to_folder("Trash", mailid);
    
    def send_to_folder(self, name, mailid):
        try:
            if name not in self.folders.keys(): return 0;
            if name == "Sent": return 0;
            cur = conn.cursor()
            cur.execute('''SELECT id FROM folders WHERE folders.name == (?)''', (name,));
            cur.execute('''INSERT INTO folders_link(mail_id, folder_id) VALUES(?,?)''', (mailid, cur.fetchall()[0][0],))
            conn.commit()
            self.folders[name][0].mails.append(mailid);
            return 1;
        except Exception as e:
            return 0;
    
    def search(self, search_string):
        x = {}
        mails = self.receive();
        new_str=r'\b'+search_string+r'\b'
        for i in mails:
            count_str=0
            # if(i.receiver.find(search_string)>=0):
            #     x.append(i)
            # if(i not in x):
            #     if(i.subject.find(search_string)>=0):
            #         x.append(i)
            # if(i not in x):
            #     if(i.body.find(search_string)>=0):
            #         x.append(i)
            if(re.search(new_str,i.receiver,flags=re.IGNORECASE )):
                m=re.findall(new_str,i.receiver,flags=re.IGNORECASE)
                count_str=count_str+len(m)
            if(re.search(new_str,i.subject,flags=re.IGNORECASE)):
                m=re.findall(new_str,i.subject,flags=re.IGNORECASE)
                count_str=count_str+len(m)
            if(re.search(new_str,i.body,flags=re.IGNORECASE)):
                m=re.findall(new_str,i.body,flags=re.IGNORECASE)
                count_str=count_str+len(m)

            if(count_str!=0):
                x[i]=count_str

        a = sorted(x.items(), key=lambda y: y[1],reverse=True)    
        x=[]
        for j in a:
            x.append(j[0])        
        return x

    def receive(self):
        mails = []
        status, messages = imap.select("INBOX")
        # number of top emails to fetch
        N = 10;
        # total number of emails
        messages = int(messages[0])
        copy_body = ""
        for i in range(messages, 0, -1):
            # fetch the email message by ID
            res, msg = imap.fetch(str(i), "(RFC822)")
            for response in msg:
                if isinstance(response, tuple):
                    # parse a bytes email into a message object
                    msg = email.message_from_bytes(response[1])
                    # decode the email subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        # if it's a bytes, decode to str
                        subject = subject.decode(encoding)
                    # decode email sender
                    From, encoding = decode_header(msg.get("From"))[0]
                    if isinstance(From, bytes):
                        From = From.decode(encoding)
                    # print("Subject:", subject)
                    # print("From:", From)

                    # if the email message is multipart
                    if msg.is_multipart():
                        # iterate over email parts
                        for part in msg.walk():
                            # extract content type of email
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            try:
                                # get the email body
                                body = part.get_payload(decode=True).decode()
                                
                            except:
                                pass
                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                # print text/plain emails and skip attachments
                                # print(body)
                                copy_body = body
                            elif "attachment" in content_disposition:
                                # download attachment
                                filename = part.get_filename()
                                if filename:
                                    folder_name = clean(subject)
                                    if not os.path.isdir(folder_name):
                                        # make a folder for this email (named after the subject)
                                        os.mkdir(folder_name)
                                    filepath = os.path.join(folder_name, filename)
                                    # download attachment and save it
                                    open(filepath, "wb").write(part.get_payload(decode=True))
                    else:
                        # extract content type of email
                        content_type = msg.get_content_type()
                        # get the email body
                        body = msg.get_payload(decode=True).decode()
                        if content_type == "text/plain":
                            # print only text email parts
                            copy_body = body

                    x = Mail(i,username,From,subject,copy_body)
                    mails.append(x)


        sql_create_projects_table = """ CREATE TABLE IF NOT EXISTS mails (
                                        id integer PRIMARY KEY,
                                        sender text NOT NULL,
                                        receiver text NOT NULL,
                                        subject text,
                                        body text
                                    ); """

        #create tables
        if conn is not None:
            # create projects table
            create_table(sql_create_projects_table)
            for mail in mails:
                m = (mail.id, mail.sender, mail.receiver, mail.subject, mail.body)
                add_vals(m)
        else:
            print("Error! cannot create the database connection.")   
        return mails


class Draft:
    def __init__(self, ob, receivers, body, file_attach, subject, mailid):
        self.sendob = ob
        self.receivers = receivers
        self.body = body
        self.file_attach = file_attach
        self.subject = subject
        self.mail_id = mailid
    
    def parse_receivers(self):
        recv = self.receivers.split(",")
        for idx in range(0, len(recv)):
            recv[idx] = recv[idx].strip()
        return recv

    def send(self):
        if(self.receivers == ""):
            self.return_err()
            return
            
        
        mailids = self.parse_receivers()
        new_recv=",".join(mailids)
        insert_sent_mails_db((self.mail_id, username, new_recv, self.subject, self.body));

        for mailid in mailids:
            s = smtplib.SMTP('smtp.gmail.com', 587)
            s.starttls()
            s.login(username, password)
            message = "Subject: " + self.subject + "\n" + self.body
            s.sendmail(username, mailid, message)
            s.quit()
        self.sendob.mails.append(Mail(self.mail_id,username,new_recv,self.subject,self.body))
        
        try:
            del drafts[self.mail_id]
        except KeyError:
            print("Key not found")

    def discard(self):
        try:
            del drafts[self.mail_id]
        except KeyError:
            pass;

    def return_err(self):
        return


class Folder:
    def __init__(self, name):
        self.name = name;
        self.mails = [];
        self.retrieve_mails_db();

    def retrieve_mails_db(self):
        try:
            cur = conn.cursor()
            cur.execute('''SELECT id FROM folders WHERE folders.name == (?)''', (self.name,));
            cur.execute('''SELECT mail_id FROM folders_link WHERE folder_id == (?)''', (cur.fetchall()[0][0],))
            for mail_id in cur.fetchall():
                self.mails.append(mail_id[0]);
            return 1;
        except Exception as e:
            return 0;

    def remove_mails(self, mailid):
        try:
            cur = conn.cursor()
            cur.execute('''DELETE FROM folders_link WHERE mail_id == (?)''', (mailid,));
            conn.commit();
            self.mails.remove(mailid);
            print(self.mails)
            return 1;
        except Exception as e:
            print(e)
            return 0;


class Sent(Folder):
    def __init__(self):
        Folder.__init__(self, "Sent");

    def retrieve_mails_db(self):
        try:
            cur = conn.cursor()
            cur.execute('''SELECT * FROM sent_mails''')
            for mail in cur.fetchall():
                self.mails.append(Mail(mail[0], mail[1], mail[2], mail[3], mail[4]))
            return 1;
        except Exception as e:
            return 0;


class Important(Folder):
    def __init__(self):
        Folder.__init__(self, "Important");


class Spam(Folder):
    def __init__(self):
        Folder.__init__(self, "Spam");


class Trash(Folder):
    def __init__(self):
        Folder.__init__(self, "Trash");


class Archive(Folder):
    def __init__(self):
        Folder.__init__(self, "Archive");


@app.route('/')
def mainpage():
    return render_template('mainpage.html')

@app.route('/mainpage.html')
def mainpage1():
    return render_template('mainpage.html')

@app.route('/send.html')
def send():
    return render_template('./send.html')

@app.route('/send_mainpage.html')
def send_mainpage():
    return render_template('./send_mainpage.html')

@app.route('/drafts.html')
def send_drafts():
    return render_template('./drafts.html')


@app.route('/sent.html', methods = ['POST', 'GET'])
def sent():
    if request.method == 'POST':
        result = request.form
        receivers = result['receiver_name']
        if(receivers == ""):
            return render_template('./err.html')
        subject = result['subject']
        body = result['body']
        draft = m.compose(receivers, subject, body)
        draft.send()
        return render_template('./sent.html')

@app.route('/err.html', methods = ['POST', 'GET'])
def err():
    return render_template('./err.html')

def delete_illusion(m, rec_mails):
    for i in range(len(m.folders["Trash"][0].mails)):
        for j in range(len(rec_mails)):
            if(m.folders["Trash"][0].mails[i]==rec_mails[j].id):
                rec_mails.pop(j)
                break;

@app.route('/receive.html', methods = ['POST', 'GET'])
def receive():
    folder=m.folders.keys()
    rec_mails=m.receive()
    delete_illusion(m, rec_mails);
    
    if(request.method=="GET"):
        return render_template('./receive.html',content=rec_mails,folder=folder)
    
    elif(request.method=="POST"):
        if request.form.get("search"):
            result=request.form['search']
            rec_mails=m.search(result)
            delete_illusion(m, rec_mails);
            return render_template('./receive.html',content=rec_mails,folder=folder)
        
        elif request.form.get("create"):
            result=request.form['create']
            m.create_folder(result)
            return render_template('./receive.html',content=rec_mails,folder=folder)
        
        elif request.form.get("Del_Folder"):
            result=request.form['Del_Folder']
            m.delete_folder(result)
            return render_template('./receive.html',content=rec_mails,folder=folder)
        
        elif request.form.get("Send1") and request.form.get("Send2"):
            try:
                folder_name=request.form['Send1']
                Mail_id=request.form['Send2']
                Mail_id=int(Mail_id)
                m.send_to_folder(folder_name,Mail_id)
            except: pass;
            finally:
                return render_template('./receive.html',content=rec_mails,folder=folder)
        
        elif request.form.get("Del_Mail"):
            try:
                Mail_id=request.form['Del_Mail']
                Mail_id=int(Mail_id)
                m.delete(Mail_id)
            except: pass;
            finally:
                delete_illusion(m, rec_mails); 
                return render_template('./receive.html',content=rec_mails,folder=folder)
        
        elif request.form.get("Rem_Mail1") and request.form.get("Rem_Mail2"):
            try:
                folder_name=request.form['Rem_Mail1']
                Mail_id=request.form['Rem_Mail2']
                Mail_id=int(Mail_id)
                if folder_name in m.folders:
                    m.folders[folder_name][0].remove_mails(Mail_id)
            except: pass;
            finally:
                return render_template('./receive.html',content=rec_mails,folder=folder)

        else:
            for k in m.folders.keys():
                if request.form.get(k):
                    if k == "Sent":
                        rec_mails = m.folders[k][0].mails;
                    else:
                        rec_mails = m.show(k);
                        if k != "Trash":
                            delete_illusion(m, rec_mails);        
                    return render_template('./receive.html',content=rec_mails,folder=folder)


if __name__ == "__main__":
    m  = MailBox()
    app.run(debug=True)
    imap.close()
    imap.logout()