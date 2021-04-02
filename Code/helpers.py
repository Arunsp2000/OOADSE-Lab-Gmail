import sqlite3
from sqlite3 import Error

def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)

def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
    return conn

# Database
database = r"data.db"
conn = create_connection(database)

def create_table(conn, create_table_sql):
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print("table: ",e)


def add_vals(conn, mails):
    try:
        sql = ''' INSERT INTO mails(id, sender, receiver, subject, body)
                  VALUES(?,?,?,?,?)'''
        
        cur = conn.cursor()
        cur.execute(sql,mails)
        conn.commit()
    except Exception as e: print(e);

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
            create_table(conn, sql_create_folder);
            create_table(conn, sql_create_folder_link);
            create_table(conn, sql_create_sent_mails);
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
        print(e)
        return 0;

def delete_folder_db(name) -> bool:
    try:
        cur = conn.cursor()
        cur.execute('''DELETE FROM folders WHERE folders.name == (?)''', (name,))
        conn.commit()
        return 1;
    except Exception as e:
        print(e)
        return 0;

def insert_sent_mails_db(mails) -> bool:
    try:
        sql = ''' INSERT INTO sent_mails(id, sender, receiver, subject, body)
                  VALUES(?,?,?,?,?)'''
        
        cur = conn.cursor()
        cur.execute(sql, mails)
        conn.commit()
    except Exception as e: print(e);