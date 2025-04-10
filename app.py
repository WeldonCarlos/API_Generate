import os
import shutil
import json
import textwrap
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, MetaData, Table
from dotenv import load_dotenv


app = Flask(__name__)
CORS(app)  # Libera para qualquer origem

@app.route('/gerar', methods=['POST'])
def gerar_backend():
    data = request.json
    db_host = data.get('db_host')
    db_name = data.get('db_name')
    db_port = data.get('db_port')
    db_user = data.get('db_user')
    db_password = data.get('db_password')
    table_name = (data.get('table_name') or '').lower()

    if not all([db_host, db_name, db_port, db_user, db_password, table_name]):
        return jsonify({"error": "Todos os campos são obrigatórios"}), 400

    project_name = f"Backend_{table_name.capitalize()}"

    try:
        engine = create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")
        connection = engine.connect()
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=engine)
        columns = table.columns.keys()
        connection.close()
    except Exception as e:
        print(f"Erro ao gerar backend: {e}")
        return jsonify({"error": str(e)}), 500

    # Criar estrutura
    os.makedirs(f"{project_name}/static", exist_ok=True)

    # .env
    env_content = f"""DB_HOST={db_host}
DB_DATABASE={db_name}
DB_PORT={db_port}
DB_USER={db_user}
DB_PASSWORD={db_password}
"""
    with open(f"{project_name}/.env", "w") as f:
        f.write(env_content)

    serialize_method = "{ " + ", ".join([f'"{col}": self.{col}' for col in columns]) + " }"
    create_fields = textwrap.indent("\n".join([f'new_item.{col} = data.get("{col}")' for col in columns if col != 'id']), '    ')
    update_fields = textwrap.indent("\n".join([f'item.{col} = data.get("{col}")' for col in columns if col != 'id']), '    ')
    model_fields = textwrap.indent("\n".join([f'{col} = db.Column(db.String(255))' for col in columns if col != 'id']), '    ')

    # app.py
    app_py = f'''# -*- coding: utf-8 -*-
import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{{os.getenv('DB_USER')}}:{{os.getenv('DB_PASSWORD')}}@{{os.getenv('DB_HOST')}}:{{os.getenv('DB_PORT')}}/{{os.getenv('DB_DATABASE')}}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

SWAGGER_URL = '/docs'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL, config={{'app_name': "CRUD API"}})
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

class {table_name.capitalize()}(db.Model):
    __tablename__ = '{table_name}'
    id = db.Column(db.Integer, primary_key=True)
{model_fields}

    def serialize(self):
        return {serialize_method}

@app.route('/{table_name}/', methods=['GET'])
def get_all():
    data = {table_name.capitalize()}.query.all()
    return jsonify([item.serialize() for item in data])

@app.route('/{table_name}/<int:id>', methods=['GET'])
def get_by_id(id):
    item = {table_name.capitalize()}.query.get_or_404(id)
    return jsonify(item.serialize())

@app.route('/{table_name}/', methods=['POST'])
def create_item():
    data = request.json
    new_item = {table_name.capitalize()}()
{create_fields}
    db.session.add(new_item)
    db.session.commit()
    return jsonify(new_item.serialize()), 201

@app.route('/{table_name}/<int:id>', methods=['PUT'])
def update_item(id):
    item = {table_name.capitalize()}.query.get_or_404(id)
    data = request.json
{update_fields}
    db.session.commit()
    return jsonify(item.serialize())

@app.route('/{table_name}/<int:id>', methods=['DELETE'])
def delete_item(id):
    item = {table_name.capitalize()}.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return '', 204

if __name__ == '__main__':
    app.run(debug=True)
'''
    with open(f"{project_name}/app.py", "w") as f:
        f.write(app_py)

    # Swagger JSON
    swagger = {
        "swagger": "2.0",
        "info": {"title": f"API {table_name.capitalize()}", "version": "1.0"},
        "basePath": "/",
        "paths": {
            f"/{table_name}/": {
                "get": {"summary": "Listar todos", "responses": {"200": {"description": "Success"}}},
                "post": {"summary": "Criar novo", "responses": {"201": {"description": "Created"}}}
            },
            f"/{table_name}/{{id}}": {
                "get": {
                    "summary": "Buscar por ID",
                    "parameters": [{"name": "id", "in": "path", "required": True, "type": "integer"}],
                    "responses": {"200": {"description": "Success"}}
                },
                "put": {
                    "summary": "Atualizar",
                    "parameters": [{"name": "id", "in": "path", "required": True, "type": "integer"}],
                    "responses": {"200": {"description": "Updated"}}
                },
                "delete": {
                    "summary": "Deletar",
                    "parameters": [{"name": "id", "in": "path", "required": True, "type": "integer"}],
                    "responses": {"204": {"description": "Deleted"}}
                }
            }
        }
    }
    with open(f"{project_name}/static/swagger.json", "w") as f:
        json.dump(swagger, f, indent=2)

    # requirements.txt
    with open(f"{project_name}/requirements.txt", "w") as f:
        f.write("Flask\nFlask-SQLAlchemy\nflask-swagger-ui\npython-dotenv\npymysql\nflask-cors\n")

    # README.md
        #with open(f"{project_name}/requirements.txt", "w") as f:
        #f.write(requirements)

    # README.md
    readme = textwrap.dedent(f"""\

        # {project_name}

        ## Instruções para rodar o projeto

        1. Instale as dependências:
        ```bash
        pip install -r requirements.txt
        ```

        2. Execute a aplicação:
        ```bash
        python app.py
        ```

        3. Acesse a documentação Swagger:
        [http://localhost:5000/docs](http://localhost:5000/docs)

        ## Descrição

        Este projeto é um CRUD para a tabela `{table_name}` gerado automaticamente. Ele inclui endpoints para criar, ler, atualizar e excluir registros, com interface Swagger.
    """)
    with open(f"{project_name}/README.md", "w", encoding="utf-8") as readme_file:
        readme_file.write(readme)

    print(f"\n✅ Projeto '{project_name}' criado com sucesso!")

    # ZIP
    shutil.make_archive(project_name, 'zip', project_name)

    return jsonify({"zip_name": f"{project_name}.zip"})

@app.route('/download/<zip_name>', methods=['GET'])
def download_zip(zip_name):
    path = os.path.join(os.getcwd(), zip_name)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({"error": "Arquivo não encontrado"}), 404

if __name__ == '__main__':
    app.run(debug=True)
