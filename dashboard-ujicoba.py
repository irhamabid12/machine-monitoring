import dash
from dash import dcc, html
from dash import dash_table as dt
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import paho.mqtt.client as mqtt
import time
import pandas as pd

machine_configs = {
    "fanuc": {"mqtt_topics": ["R01/ON", "R02/ON", "R12/OFF"]},
}

mqtt_server = "127.0.0.1"

app = dash.Dash(__name__, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])

def format_time(seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))

class RealTimeMonitor:
    def __init__(self, machine_name, mqtt_server, mqtt_topics):
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
        config["mqtt_topics"],
    )
    machines[machine_name] = machine

button_group = dbc.ButtonGroup([ 
    dbc.Button("Dashboard", id="btn-dashboard", n_clicks=0, className="btn-nav"),
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

initial_data = {
    machine: {'run_seconds': 0, 'idle_seconds': 0, 'down_seconds': 0, 'total_time': 0, 'run_percent': 0, 'idle_percent': 0, 'down_percent': 0} for machine in machine_configs
}

app.layout = dbc.Container([
    html.Div(className="header", children=[
        dbc.Button(html.I(className="bi bi-house-door"), href="/", id="home-btn", className="home-btn", color="primary"),
        html.H1("    Real-time Monitoring System", id='main-title')
    ]),
    dcc.Store(id='monitor-store', storage_type='session', data=initial_data),
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content'),
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0),
], fluid=True, id="app-container")

@app.callback(
    [Output('url', 'pathname')],
    [Input('btn-dashboard', 'n_clicks')],
    [State('url', 'pathname')]
)
def update_url(btn_dashboard, pathname):
    ctx = dash.callback_context
    if not ctx.triggered_id:
        button_id = 'btn-dashboard'
    else:
        button_id = ctx.triggered_id.split('.')[0]

    machine = pathname.split('/')[1]
    current_path = f'/{machine}'

    if button_id == 'btn-dashboard':
        return [f'{current_path}']

@app.callback([Output("page-content", "children"),
               Output('home-btn', 'style'),
               Output('main-title', 'style')],
              [Input('url', 'pathname')])
def display_page(pathname):
    machine = pathname.split('/')[1]
    if machine and machine in machine_configs:
        return dashboard_layouts[machine], {'display': 'flex'}, {}
    else:
        return main_layout, {'display': 'none'}, {'marginTop': '8rem'}

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

if __name__ == '__main__':
    try:
        app.run(debug=True, host='127.0.0.1', port=8080)
    except KeyboardInterrupt:
        print("\nScript terminated.")
