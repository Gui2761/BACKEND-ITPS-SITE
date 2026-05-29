import sqlite3
import psycopg2
import os

# --- CONFIGURAÇÕES DE CONEXÃO ---
PG_HOST = "172.23.6.109"
PG_PORT = 5432
PG_USER = "geinform"
PG_PASSWORD = "intr@bd109"
PG_DB = "bd_intranet"

DB_CONTRATOS_PATH = r"\\172.23.6.7\ageplan\Banco de contratos\banco_contratos.db"
DB_FOLHA_PATH = r"\\172.23.6.7\gerh\1- COAPE\FolhaITPS_Dados\folha_itps_v8_rh_sync.db"

def map_sqlite_type_to_pg(sqlite_type, col_name, is_pk):
    sqlite_type = sqlite_type.upper()
    if is_pk and "INT" in sqlite_type:
        return "SERIAL PRIMARY KEY"
    if "INT" in sqlite_type:
        return "INTEGER"
    if "REAL" in sqlite_type or "NUMERIC" in sqlite_type or "FLOAT" in sqlite_type or "DOUBLE" in sqlite_type:
        return "DOUBLE PRECISION"
    if "BLOB" in sqlite_type:
        return "BYTEA"
    return "TEXT"

def migrar_banco(sqlite_path, schema_name):
    print(f"\n--- Iniciando migração de: {sqlite_path} para o schema PG '{schema_name}' ---")
    
    if not os.path.exists(sqlite_path):
        print(f"ERRO: Arquivo SQLite não encontrado no caminho: {sqlite_path}")
        return
        
    # Conecta no SQLite
    conn_sq = sqlite3.connect(sqlite_path)
    cursor_sq = conn_sq.cursor()
    
    # Conecta no PostgreSQL
    conn_pg = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DB
    )
    cursor_pg = conn_pg.cursor()
    
    # Garante que o schema existe
    cursor_pg.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
    conn_pg.commit()
    
    # Lista todas as tabelas do SQLite
    cursor_sq.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor_sq.fetchall()]
    
    for table in tables:
        print(f"\nProcessando tabela: {table}")
        
        # Pega a estrutura da tabela no SQLite
        cursor_sq.execute(f"PRAGMA table_info({table});")
        columns_info = cursor_sq.fetchall()
        
        # Cria a tabela no PostgreSQL
        pg_cols = []
        col_names = []
        has_id = False
        
        for col in columns_info:
            cid, name, col_type, notnull, dflt_value, pk = col
            is_pk = (pk == 1)
            pg_type = map_sqlite_type_to_pg(col_type, name, is_pk)
            
            if name.lower() == 'id' and is_pk:
                has_id = True
                
            # Escapa nomes reservados do postgres
            col_def = f'"{name}" {pg_type}'
            pg_cols.append(col_def)
            col_names.append(name)
            
        create_query = f'CREATE TABLE IF NOT EXISTS {schema_name}."{table}" ({", ".join(pg_cols)});'
        print(f"Criando tabela com query: {create_query}")
        cursor_pg.execute(create_query)
        conn_pg.commit()
        
        # Limpa tabela se já existisse (para evitar duplicidade na migração)
        cursor_pg.execute(f'TRUNCATE TABLE {schema_name}."{table}" RESTART IDENTITY CASCADE;')
        conn_pg.commit()
        
        # Busca os dados no SQLite
        cursor_sq.execute(f'SELECT * FROM "{table}";')
        rows = cursor_sq.fetchall()
        
        if not rows:
            print(f"Tabela {table} vazia no SQLite.")
            continue
            
        # Prepara a inserção no PostgreSQL
        escaped_cols = [f'"{c}"' for c in col_names]
        placeholders = [f"%s" for _ in col_names]
        insert_query = f'INSERT INTO {schema_name}."{table}" ({", ".join(escaped_cols)}) VALUES ({", ".join(placeholders)});'
        
        print(f"Inserindo {len(rows)} linhas na tabela {table}...")
        cursor_pg.executemany(insert_query, rows)
        conn_pg.commit()
        
        # Se a tabela tem coluna 'id' autoincremento (SERIAL), atualiza a sequência no PG
        if has_id:
            seq_query = f"SELECT setval(pg_get_serial_sequence('{schema_name}.\"{table}\"', 'id'), COALESCE(MAX(id), 1)) FROM {schema_name}.\"{table}\";"
            try:
                cursor_pg.execute(seq_query)
                conn_pg.commit()
                print(f"Sequência atualizada para tabela {table}.")
            except Exception as e:
                conn_pg.rollback()
                print(f"Aviso ao atualizar sequência para {table}: {e}")
                
    conn_sq.close()
    conn_pg.close()
    print(f"\n--- Migração concluída com sucesso para o schema: {schema_name}! ---")

if __name__ == "__main__":
    # Migra os dois bancos
    migrar_banco(DB_CONTRATOS_PATH, "contratos")
    migrar_banco(DB_FOLHA_PATH, "folha")
