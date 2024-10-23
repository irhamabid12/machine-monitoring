import dash
from dash import dcc, html
from dash import dash_table as dt
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import paho.mqtt.client as mqtt
import mysql.connector
import time
import pandas as pd

machine_configs = {
    "fanuc": {"mqtt_topics": ["R01/ON", "R02/ON", "R12/OFF"]},
}

mqtt_server = "192.168.1.7"

mysql_config = {
    "host": "localhost",
    "user": "root",
    "password": "12345",
    "database": "machine",
}

app = dash.Dash(__name__, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])

def format_time(seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))

class RealTimeMonitor:
    def __init__(self, machine_name, mqtt_server, mysql_config, mqtt_topics):
        self.machine_name = 'fanuc'
        self.run_increment = False
        self.idle_increment = False
        self.down_increment = False
        self.run_seconds = 0
        self.idle_seconds = 0
        self.down_seconds = 0
        self.total_seconds = 0

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(mqtt_server, 1883, 0)
        self.full_topic = [f"fanuc/{topic}" for topic in mqtt_topics]
        self.client.loop_start()

        self.fetch_initial_counters()

    # Fetch the required data from the MySQL database
    def fetch_data_from_mysql(self, start_date, end_date):
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM fanuc WHERE date BETWEEN %s AND %s", (start_date, end_date))
        data = cursor.fetchall()
        cursor.close()
        connection.close()
        return data

    # Fetch the oee
    def fetch_oee_data(self):
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM oee WHERE date = CURDATE() AND id = 'fanuc'")
        data = cursor.fetchall()
        cursor.close()
        connection.close()
        return data

    def fetch_initial_counters(self):
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor(dictionary=True)

        # SQL query to calculate total duration for each status for the current date
        sql_query = f"SELECT status, SUM(CASE WHEN end_time IS NOT NULL THEN TIME_TO_SEC(duration)ELSE TIMESTAMPDIFF(SECOND, start_time, NOW()) END) as total_duration FROM fanuc GROUP BY status;"
        cursor.execute(sql_query)

        # Process fetched data and update counters
        for row in cursor.fetchall():
            status = row['status']
            total_duration = row['total_duration']

            if status == 'RUNNING':
                self.run_seconds = total_duration
            elif status == 'IDLE':
                self.idle_seconds = total_duration
            elif status == 'DOWN':
                self.down_seconds = total_duration

            self.total_seconds += total_duration

        cursor.close()
        connection.close()

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        for topic in self.full_topic:
            client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        print(f"{msg.topic}: {msg.payload.decode()}")
        c = msg.payload.decode()

        if msg.topic == self.full_topic[0]:
            self.run_increment = (c == "true")
        elif msg.topic == self.full_topic[1]:
            self.down_increment = (c == "true")
        elif msg.topic == self.full_topic[2]:
            self.idle_increment = (c == "true")

    def update_time(self):
        if self.run_increment:
            self.run_seconds += 1
        elif self.idle_increment:
            self.idle_seconds += 1
        elif self.down_increment:
            self.down_seconds += 1

        self.total_seconds = self.run_seconds + self.idle_seconds + self.down_seconds

    def get_time_data(self):
        runtime = format_time(self.run_seconds)
        idletime = format_time(self.idle_seconds)
        downtime = format_time(self.down_seconds)
        total_time = format_time(self.total_seconds)
        runtime_percent = (self.run_seconds / self.total_seconds) * 100 if self.total_seconds > 0 else 0
        idletime_percent = (self.idle_seconds / self.total_seconds) * 100 if self.total_seconds > 0 else 0
        downtime_percent = (self.down_seconds / self.total_seconds) * 100 if self.total_seconds > 0 else 0

        return runtime, idletime, downtime, total_time, runtime_percent, idletime_percent, downtime_percent

# Define a specific configuration for the 'fanuc' machine
machine_configs = {
    "fanuc": {
        "mqtt_topics": ["status", "metrics"]  # Example topics; adjust as needed
    }
}

# Create instances for each machine
machines = {}
for machine_name, config in machine_configs.items():
    machine = RealTimeMonitor(
        machine_name,
        mqtt_server,
        mysql_config,
        config["mqtt_topics"],
    )
    machines[machine_name] = machine

button_group = dbc.ButtonGroup([
    dbc.Button("Dashboard", id="btn-dashboard", n_clicks=0, className="btn-nav"),
    dbc.Button("Database", id="btn-database", n_clicks=0, className="btn-nav"),
    dbc.Button("OEE", id="btn-oee", n_clicks=0, className="btn-nav"),
], className="btn_group")

main_layout = dbc.Container([
    dbc.Col([
        dcc.Link(
            dbc.Button(f"{machine.capitalize()}", className="mch-btn", id=f"{machine}-btn", n_clicks=0),
            href=f"/{machine}",
        )
    ]) for machine in machine_configs
], fluid=True, id="main-container", className="main-container")

dashboard_layouts = {
    machine: dbc.Container([
        html.Div(children=[
            html.H1(machine.capitalize(), id="dashboard-title", className="mch-title")
        ]),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Label("Current Date: ", className="label-text"),
                    html.Span(id='live-date', className="live-date"),
                ], className="text-center my-2"),
                
                html.Div([
                    html.Label("Current Time: ", className="label-text"),
                    html.Span(id='live-time', className="live-time"),
                ], className="text-center my-2"),
            ], width=8)
        ], justify="center"),
        
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Label("Production Time: ", className="label-text"),
                    html.Span(id='total-time', className="live-time"),
                ], className="text-center my-2")
            ], width=8)
        ], justify="center"),

        dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card(className="card", children=[
                        dbc.CardBody([
                            html.P("Run Time", className="card-text text-center"),
                            dbc.Progress(id="runtime-progress", value=50, max=100, striped=True, className="card-progress"),
                            html.P(id='runtime-time', className="card-text text-center")
                        ], style={"border": "solid green"})
                    ])
                ], width=4),
                
                dbc.Col([
                    dbc.Card(className="card", children=[
                        dbc.CardBody([
                            html.P("Idle Time", className="card-text text-center"),
                            dbc.Progress(id="idletime-progress", value=30, max=100, striped=True, className="card-progress"),
                            html.P(id='idletime-time', className="card-text text-center")
                        ], style={"border": "solid yellow"})
                    ])
                ], width=4),
                
                dbc.Col([
                    dbc.Card(className="card", children=[
                        dbc.CardBody([
                            html.P("Down Time", className="card-text text-center"),
                            dbc.Progress(id="downtime-progress", value=20, max=100, striped=True, className="card-progress"),
                            html.P(id='downtime-time', className="card-text text-center")
                        ], style={"border": "solid red"})
                    ])
                ], width=4)
            ], justify="center", className="container")
        ]),

        button_group
    ], fluid=True, id=f"{machine}-page") for machine in machine_configs
}

database_layout = {
    machine: dbc.Container([
        html.Div(children=[
            html.H1(machine.capitalize(), id="dashboard-title", className="mch-title")
        ]),

        dbc.Row([
            # dbc.Col([
            dcc.DatePickerRange(
                id='date-picker-range',
                start_date=time.strftime("%Y-%m-%d"),
                end_date=time.strftime("%Y-%m-%d"),
                display_format='DD MMMM YYYY',
                minimum_nights=0,
                clearable=True,
                className="date-picker"
            ),
            # ], className="date-column"),        
            # dbc.Col([
            dbc.Button("Download Data", id="btn-download", n_clicks=0, className="btn-download", color="primary"),
            dcc.Download(id="download-data")
            # ], className="btn-column")
        ], className="date-picker-row"),

        dbc.Row([
            dbc.Col([
                dt.DataTable(id='datatable',
                            columns=[
                                {"name": "Date", "id": "date"},
                                {"name": "Start Time", "id": "start_time"},
                                {"name": "End Time", "id": "end_time"},
                                {"name": "Duration", "id": "duration"},
                                {"name": "Status", "id": "status"}
                            ],
                            cell_selectable=False,
                            style_table={'bordered': True, 'marginBottom': '6rem'},  # Add border to the table
                            style_cell={'textAlign': 'center', 'color': 'white'},  # Center align the cell content
                            style_header={'backgroundColor': 'darkslategrey'},
                            style_data={'backgroundColor': 'grey'},
                            style_data_conditional=[
                                {
                                    'if': {'column_id': 'status', 'filter_query': '{status} = "RUNNING"'},
                                    'backgroundColor': 'seagreen',
                                },
                                {
                                    'if': {'column_id': 'status', 'filter_query': '{status} = "IDLE"'},
                                    'backgroundColor': 'goldenrod',
                                },
                                {
                                    'if': {'column_id': 'status', 'filter_query': '{status} = "DOWN"'},
                                    'backgroundColor': 'firebrick',
                                }
                            ],
                            data=[]),
            ]),
        ]),
        button_group
    ], fluid=True, id="database-page") for machine in machine_configs
}

oee_layout = {
    machine: dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H3(machine.capitalize(), className="part-header"),
                dbc.Row([
                    dbc.Col([
                        dt.DataTable(id='andontable',
                                    columns=[
                                        {"name": "Plan", "id": "plan"},
                                        {"name": "Actual", "id": "actual"}
                                    ],
                                    cell_selectable=False,
                                    style_table={'bordered': True, 'marginBottom': '1rem'},
                                    style_cell={'textAlign': 'center', 'color': 'white'},  # Center align the cell content
                                    style_header={'backgroundColor': 'darkslategrey'},
                                    style_data={'backgroundColor': 'grey', 'fontSize': '4rem', 'padding': '1.5rem'},
                                    data=[]),
                    ]),
                ]),        
                dbc.Row([
                    dbc.Button(html.I(className="bi bi-download"), id="oee-download", n_clicks=0, color="primary"),
                    dcc.Download(id="download-oee")
                ], style={"paddingLeft": "3rem", "width": "fit-content"})
            ], width=7),
            dbc.Col([
                dbc.Card(className="card-oee", children=[
                    dbc.CardBody([
                        html.P(id="percentage", className="oee-percent")
                    ], style={"border": "solid white"}, className="card-oee-body")
                ])
            ], width=5, className="oee-col"),
        ], className="oee-row"),

        button_group
    ], fluid=True, id="oee-page") for machine in machine_configs
}

initial_data = {
    machine: {'run_seconds': 0, 'idle_seconds': 0, 'down_seconds': 0, 'total_time': 0, 'run_percent': 0, 'idle_percent': 0, 'down_percent': 0} for machine in machine_configs
}

app.layout = dbc.Container([
    html.Div(className="header", children=[
        dbc.Button(html.I(className="bi bi-house-door"), href="/", id="home-btn", className="home-btn", color="primary"),
        html.H1("ISUZU Real-time Monitoring System", id='main-title')
    ]),
    dcc.Store(id='monitor-store', storage_type='session', data=initial_data),
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content'),
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0),
], fluid=True, id="app-container")

@app.callback(
    [Output('url', 'pathname')],
    [Input('btn-dashboard', 'n_clicks'),
     Input('btn-database', 'n_clicks'),
     Input('btn-oee', 'n_clicks')],
    [State('url', 'pathname')]
)
def update_url(btn_dashboard, btn_database, btn_oee, pathname):
    ctx = dash.callback_context
    if not ctx.triggered_id:
        button_id = 'btn-dashboard'
    else:
        button_id = ctx.triggered_id.split('.')[0]

    machine = pathname.split('/')[1]
    current_path = f'/{machine}'

    if button_id == 'btn-dashboard':
        return [f'{current_path}']
    elif button_id == 'btn-database':
        return [f'{current_path}/database']
    elif button_id == 'btn-oee':
        return [f'{current_path}/oee']

# Callback to update machine and display the corresponding dashboard_layout
@app.callback([Output("page-content", "children"),
               Output('home-btn', 'style'),
               Output('main-title', 'style')],
              [Input('url', 'pathname')])
def display_page(pathname):
    machine = pathname.split('/')[1]
    if machine and machine in machine_configs:
        if machine in dashboard_layouts:
            if pathname.endswith('/database'):
                if machine in database_layout:
                    return database_layout[machine], {'display': 'flex'}, {}
                else:
                    # If database hasn't been created
                    return dbc.Container([
                        html.H1(f"No Database Layout for {machine}", id="dashboard-title", style={"color": "red"})
                    ])
            elif pathname.endswith('/oee'):
                if machine in oee_layout:
                    return oee_layout[machine], {'display': 'flex'}, {}
            else:
                return dashboard_layouts[machine], {'display': 'flex'}, {}
    else:
        # Default to the dashboard page if the URL path is unrecognized
        return main_layout, {'display': 'none'}, {'marginTop': '8rem'}

@app.callback(
    [Output('btn-dashboard', 'active'),
     Output('btn-database', 'active'),
     Output('btn-oee', 'active')],
    [Input('url', 'pathname')]
)
def update_button_state(pathname):
    machine = pathname.split('/')[1]

    if pathname == f'/{machine}':
        return True, False, False
    elif pathname.endswith('/database'):
        return False, True, False
    elif pathname.endswith('/oee'):
        return False, False, True

@app.callback(
    [Output('live-date', 'children'),
     Output('live-time', 'children'),
     Output('runtime-time', 'children'),
     Output('idletime-time', 'children'),
     Output('downtime-time', 'children'),
     Output('total-time', 'children'),
     Output('runtime-progress', 'value'),
     Output('idletime-progress', 'value'),
     Output('downtime-progress', 'value')],
    [Input('monitor-store', 'data')],
    [State('url', 'pathname')]
)
def update_ui(data, pathname):
    machine = pathname.split('/')[1]
    date = time.strftime("%Y-%m-%d")
    clock = time.strftime("%H:%M:%S")
    runtime = data[machine]['run_seconds']
    idletime = data[machine]['idle_seconds']
    downtime = data[machine]['down_seconds']
    total_time = data[machine]['total_time']
    run_percent = data[machine]['run_percent']
    idle_percent = data[machine]['idle_percent']
    down_percent = data[machine]['down_percent']

    return (date, clock, runtime, idletime, downtime, total_time, 
            run_percent, idle_percent, down_percent)

@app.callback( 
    Output('monitor-store', 'data'),
    [Input('interval-component', 'n_intervals')],
    [State('monitor-store', 'data')])
def store_data(n_intervals, data):
    for mch in machine_configs:
        monitor = machines[mch]
        monitor.update_time()

        runtime, idletime, downtime, total_time, run_percent, idle_percent, down_percent = monitor.get_time_data()
        data[mch]['run_seconds'] = runtime
        data[mch]['idle_seconds'] = idletime
        data[mch]['down_seconds'] = downtime
        data[mch]['total_time'] = total_time
        data[mch]['run_percent'] = run_percent
        data[mch]['idle_percent'] = idle_percent
        data[mch]['down_percent'] = down_percent
    return data

# Define the callback to update the table content
@app.callback(
        Output('datatable', 'data'), 
        [Input('interval-component', 'n_intervals'),
         Input('date-picker-range', 'start_date'),
         Input('date-picker-range', 'end_date')],
        [State('url', 'pathname')])
def update_table(n_intervals, start_date, end_date, pathname):
    machine = pathname.split('/')[1]
    monitor = machines[machine]
    data = monitor.fetch_data_from_mysql(start_date, end_date)
    return [{'date': str(row[0]), 'start_time': str(row[1]), 'end_time': str(row[2]), 'duration': str(row[3]), 'status': row[4]} for row in data]

@app.callback(
    Output("download-data", "data"),
    [Input("btn-download", "n_clicks"),
     State('date-picker-range', 'start_date'),
     State('date-picker-range', 'end_date'),
     State('url', 'pathname')],
    prevent_initial_call=True
)
def download_data(n_clicks, start_date, end_date, pathname):
    if n_clicks:
        machine = pathname.split('/')[1]
        monitor = machines[machine]
        data = monitor.fetch_data_from_mysql(start_date, end_date)
        df = pd.DataFrame(data, columns=["date", "start_time", "end_time", "duration", "status"])
        df['start_time'] = df['start_time'].apply(lambda x: str(x).split()[-1])
        df['end_time'] = df['end_time'].apply(lambda x: str(x).split()[-1])
        df['duration'] = df['duration'].apply(lambda x: str(x).split()[-1])
        return dcc.send_data_frame(df.to_excel, filename=f"{machine}.xlsx", index=False)
    return None

@app.callback(
    Output("download-oee", "data"),
    [Input("oee-download", "n_clicks"),
     State('url', 'pathname')],
    prevent_initial_call=True
)
def download_oee(n_clicks, pathname):
    if n_clicks:
        machine = pathname.split('/')[1]
        monitor = machines[machine]
        data = monitor.fetch_oee_data()
        df = pd.DataFrame(data, columns=["id", "date", "plan", "actual", "percentage"])
        return dcc.send_data_frame(df.to_excel, filename=f"{machine}.xlsx", index=False)
    return None

@app.callback(
        [Output('andontable', 'data'), 
         Output('percentage', 'children')],
        [Input('interval-update-actual', 'n_intervals')],
        [State('url', 'pathname')])
def update_andon(n_intervals, pathname):
    machine = pathname.split('/')[1]
    monitor = machines[machine]
    data = monitor.fetch_oee_data()
    for row in data:
        plan = row[2]
        actual = row[3]
        percentage = row[4]
    return [{'plan': plan, 'actual': actual}], percentage 

if __name__ == '__main__':
    try:
        app.run(debug=True, host='0.0.0.0', port=8080)
    except KeyboardInterrupt:
        print("\nScript terminated.")

