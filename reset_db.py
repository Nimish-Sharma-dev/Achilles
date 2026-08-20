import sqlite3
conn = sqlite3.connect('gridsentinel.db')
conn.execute('UPDATE nodes SET status="HEALTHY", current_hash=golden_hash')
conn.execute('UPDATE attacks SET active=0')
conn.execute('DELETE FROM alerts')
conn.commit()
conn.close()
print("Reset complete.")