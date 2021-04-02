import sys
import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.header import Header
from email import encoders

import imaplib
import email
from email.header import decode_header
import webbrowser
import os

import sqlite3
from sqlite3 import Error

from helpers import *

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
    
    def compose(self):
        receivers = input("Enter receiver(s): ")
        subject = input("Enter subject: ")
        body = input("Enter body: ")
        file_name = input("Enter file name (if needed else blank): ")
        mail_id = len(self.folders["Sent"][0].mails)+1;
        compose_mail = Draft(self.folders["Sent"][0], receivers, body, file_name, subject, mail_id)
        drafts[mail_id] = compose_mail
        return compose_mail
    
    def create_folder(self, name):
        if name not in self.folders:
            self.folders[name] = Folder(name);
            insert_folder_db(name, 0);
            print("Folder Created")
        else:
            print("Folder Already Exists")
    
    def delete_folder(self, name):
        if name in self.folders:
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
            print(e)
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
            print(e)
            return 0;
    
    def search(self, search_string):
        x = []
        mails = self.receive();
        for i in mails:
            if(i.receiver.find(search_string)>=0):
                x.append(i)
            if(i not in x):
                if(i.subject.find(search_string)>=0):
                    x.append(i)
            if(i not in x):
                if(i.body.find(search_string)>=0):
                    x.append(i)
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
                    print("Subject:", subject)
                    print("From:", From)

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
                                print(body)
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
                            print(body)
                            copy_body = body

                    print("=" * 100)
                    x = Mail(messages-i,username,From,subject,copy_body)
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
            create_table(conn, sql_create_projects_table)
            for mail in mails:
                m = (mail.id, mail.sender, mail.receiver, mail.subject, mail.body)
                add_vals(conn, m)
        else:
            print("Error! cannot create the database connection.")
        imap.close()
        imap.logout()     
        return mails


class Draft:
    def __init__(self, ob, receivers, body, file_attach, subject, mailid):
        self.sendob = ob;
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
            print("Error!")
            sys.exit(0)
        
        mailids = self.parse_receivers()

        for mailid in mailids:
            s = smtplib.SMTP('smtp.gmail.com', 587)
            s.starttls()
            s.login(username, password)
            message = "Subject: " + self.subject + "\n" + self.body
            s.sendmail(username, mailid, message)
            s.quit()
            insert_sent_mails_db((self.mail_id, username, mailid, self.subject, self.body));
            self.sendob.mails.append(self.mail_id)
            del drafts[self.mail_id]
    
    def discard(self):
        del drafts[self.mail_id]


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
            print(e)
            return 0;

    def remove_mails(self, mailid):
        try:
            cur = conn.cursor()
            cur.execute('''DELETE FROM folders_link WHERE mail_id == (?)''', (mailid,));
            conn.commit();
            self.mails.remove(mailid);
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
            cur.execute('''SELECT id FROM sent_mails''')
            for mail_id in cur.fetchall():
                self.mails.append(mail[0]);
            return 1;
        except Exception as e:
            print(e)
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


if __name__ == "__main__":
    m  = MailBox()
    # m.receive();
    # print(m.search("loop"));
    # m.create_folder(input("Folder? "))
    print(m.folders.keys())
    sql = '''SELECT * FROM folders'''
            
    cur = conn.cursor()
    cur.execute(sql)
    for i in cur.fetchall():
        print(i)
    x = input("Folder? ");
    # m.send_to_folder(x, 2)
    m.folders[x][0].remove_mails(2);
    print(m.folders[x][0].mails);
    print(m.show(x));
    sql = '''SELECT * FROM folders_link'''
            
    cur = conn.cursor()
    cur.execute(sql)
    for i in cur.fetchall():
        print(i)
    # conn.commit()
    # print("HERE: ", m.folders["Sent"][0].mails);
    
    # m.receive()
    # sql = '''SELECT * FROM sent_mails'''
            
    # cur = conn.cursor()
    # cur.execute(sql)
    # for i in cur.fetchall():
    #     print(i)

        




        