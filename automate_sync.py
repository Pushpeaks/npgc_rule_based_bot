import os
import pymysql
import requests
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
LOCAL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pushpesh@1104',
    'database': 'collegemanagementsoftware',
    'cursorclass': pymysql.cursors.DictCursor
}

CLOUD_CONFIG = {
    'host': os.getenv("TIDB_HOST"),
    'user': os.getenv("TIDB_USER"),
    'password': os.getenv("TIDB_PASSWORD"),
    'database': os.getenv("TIDB_DB"), 
    'port': int(os.getenv("TIDB_PORT", 4000)),
    'ssl': {'ca': os.getenv("TIDB_CA_PATH")}
}

BOT_REFRESH_URL = "http://localhost:8000/refresh"

def sync():
    print("--- NPGC Automated Knowledge Sync & Cloud Migration ---")
    
    try:
        print("\n1. Connecting to Local & Cloud Databases...")
        local_conn = pymysql.connect(**LOCAL_CONFIG)
        cloud_conn = pymysql.connect(**CLOUD_CONFIG)
        
        with local_conn.cursor() as local_cur, cloud_conn.cursor() as cloud_cur:
            
            # PHASE 1: ENSURE LOCAL KNOWLEDGE IS CORRECT
            print("\n2. Updating Local Knowledge (BCA & Faculty)...")
            
            # Ensure Dept ID 1 is Computer Science
            local_cur.execute("SELECT deptId FROM department WHERE deptName LIKE '%Computer Science%'")
            dept = local_cur.fetchone()
            dept_id = dept['deptId'] if dept else 1 # Default to 1 if exists, or should we create?
            
            # Update BCA Course
            local_cur.execute("UPDATE course SET deptId = %s WHERE course LIKE %s OR course LIKE %s", 
                            (dept_id, "%BCA%", "%Bachelor of Computer Applications%"))
            
            # Add/Update Dr. Gaurvi Shukla
            local_cur.execute("SELECT facultyId FROM faculty WHERE name LIKE '%Gaurvi Shukla%'")
            faculty = local_cur.fetchone()
            if not faculty:
                local_cur.execute("INSERT INTO faculty (name, designation, deptId, qualification) VALUES (%s, %s, %s, %s)",
                                ("Dr. Gaurvi Shukla", "Assistant Professor", dept_id, "Ph.D."))
            else:
                local_cur.execute("UPDATE faculty SET designation = 'Assistant Professor', deptId = %s WHERE facultyId = %s",
                                (dept_id, faculty['facultyId']))
            
            local_conn.commit()
            print("   [OK] Local knowledge synchronized.")

            # PHASE 2: MIGRATE TO CLOUD
            tables = ["department", "coursetype", "course", "faculty", "faqs", "chatbotknowledge"]
            for table in tables:
                print(f"\n3. Migrating table: {table}...")
                
                # Get schema
                local_cur.execute(f"DESCRIBE `{table}`")
                columns_desc = local_cur.fetchall()
                
                col_defs = []
                primary_key = None
                for col in columns_desc:
                    null = "NOT NULL" if col['Null'] == "NO" else "NULL"
                    col_def = f"`{col['Field']}` {col['Type']} {null} {col['Extra']}"
                    col_defs.append(col_def)
                    if col['Key'] == "PRI": primary_key = col['Field']
                if primary_key: col_defs.append(f"PRIMARY KEY (`{primary_key}`)")
                
                cloud_cur.execute(f"DROP TABLE IF EXISTS `{table}`")
                cloud_cur.execute(f"CREATE TABLE `{table}` ({', '.join(col_defs)})")
                
                # Transfer Data
                local_cur.execute(f"SELECT * FROM `{table}`")
                rows = local_cur.fetchall()
                if rows:
                    columns = rows[0].keys()
                    placeholders = ", ".join(["%s"] * len(columns))
                    insert_sql = f"INSERT INTO `{table}` ({', '.join(['`'+c+'`' for c in columns])}) VALUES ({placeholders})"
                    for row in rows:
                        cloud_cur.execute(insert_sql, list(row.values()))
                    print(f"   [OK] Migrated {len(rows)} records.")
                else:
                    print("   [INFO] No records found.")

            cloud_conn.commit()
            print("\nALL DATA MIGRATED SUCCESSFULLY TO TIDB CLOUD!")

    except Exception as e:
        print(f"\n[ERROR] during sync: {str(e)}")
    finally:
        if 'local_conn' in locals(): local_conn.close()
        if 'cloud_conn' in locals(): cloud_conn.close()

    # PHASE 3: REFRESH BOT ENGINE
    print("\n4. Notifying Chatbot to Refresh Memory...")
    try:
        resp = requests.get(BOT_REFRESH_URL, timeout=5)
        if resp.status_code == 200:
            print("   [OK] Bot memory refreshed live!")
        else:
            print(f"   [WARN] Could not refresh bot memory (Server returned {resp.status_code}). Is the server running?")
    except:
        print("   [WARN] Server not reachable for live refresh. Restart it manually if it's running elsewhere.")

if __name__ == "__main__":
    sync()
