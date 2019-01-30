from flask import Flask
from flask import g
from flask import jsonify
from flask import request
from flask_restful import reqparse, abort, Api, Resource
import sqlite3
import json
from datetime import datetime
import time
import math

DATABASE = 'C:/Users/Jasper/Downloads/parking_db.db'

app = Flask(__name__)
api = Api(app)

conn = sqlite3.connect(DATABASE, check_same_thread=False)
cur = conn.cursor()

parser = reqparse.RequestParser()
parser.add_argument('limit', type=int, help='Parameter "limit" should be of type integer')
parser.add_argument('start', type=int, help='Parameter "start" should be of type integer')
parser.add_argument('end', type=int, help='Parameter "end" should be of type integer')
parser.add_argument('interval', type=int, help='Parameter "interval" should be of type integer')
parser.add_argument('page', type=int, help='Parameter "page" should be of type integer')

# Function to query to database, returning all rows
def dbQuery(query):
    cur.execute(query)
    rows = cur.fetchall()
    return rows

#Class for single sector
class Sector(Resource):
    def options(self, sector_id):
        return '', 204, {'Allow': 'GET, OPTIONS'}
    def get(self, sector_id):
        result = dbQuery('SELECT entry.timestamp, entry.density, entry.cluster_id, coordinate.latitude, coordinate.longtitude, sensor.id, sensor.parked FROM entry INNER JOIN coordinate ON coordinate.sector_id = entry.cluster_id INNER JOIN sensor ON sensor.sector_id = entry.cluster_id WHERE cluster_id = ' + sector_id + ' AND entry.timestamp = (SELECT MAX(entry.timestamp) FROM entry)  ORDER BY timestamp DESC')
        if len(result) <= 0:
            abort(404, message="Sector {} doesn't exist".format(sector_id))
        
        items = [dict(zip([key[0] for key in cur.description], row)) for row in result]
        coordinates = []
        sensors = []
        threshold = 0
        count = 0
        response = []
   
        for val in items:   
            timestamp = int(val['timestamp'] / 1000) 
            readable = datetime.fromtimestamp(timestamp).isoformat()

            skip = False
            sensorExists = False
            if count < 1:
                threshold = val['timestamp']
                response.append({
                'data': {
                    'sector_id': val['cluster_id'],
                    'density': val['density'],
                    'timestamp': timestamp,
                    'date': readable
                    }
                })
            if val['timestamp'] >= threshold :
                for cor in coordinates:
                    if cor['latitude'] == val['latitude'] and cor['longitude'] == val['longtitude']:
                        skip = True
                        break

                for sen in sensors:
                    if sen['id'] == val['id']:
                        sensorExists = True
                        break
                
                if skip == False:
                    coordinates.append({'latitude': val['latitude'], 'longitude': val['longtitude']})
                if sensorExists == False:
                    sensors.append({'id': val['id'], 'parked': val['parked']})
            else :
                break
            count = count + 1
        response[0]['data']['coordinates'] = coordinates
        response[0]['data']['sensors'] = sensors
        return response

#Class for all sectors collection
class Sectors(Resource):
    def options(self):
        return '', 204, {'Allow': 'GET, OPTIONS'}
    def get(self):
        response = []
        coordinates = []
        sectors = []
        sensors = []
        threshold = 0
        count = 0
        root = str(request.url_root)

        idResult = dbQuery('SELECT id FROM sector')
        idItems = [dict(zip([key[0] for key in cur.description], row)) for row in idResult]
        for val in idItems:
            response.append({
                'data': {
                    'sector_id': val['id']
                }})

        result = dbQuery('SELECT entry.timestamp, entry.density, entry.cluster_id, coordinate.latitude, coordinate.longtitude, sensor.id, sensor.parked FROM entry INNER JOIN coordinate ON coordinate.sector_id = entry.cluster_id INNER JOIN sensor ON sensor.sector_id = entry.cluster_id WHERE entry.timestamp = (SELECT MAX(entry.timestamp) FROM entry)  ORDER BY timestamp DESC')
        items = [dict(zip([key[0] for key in cur.description], row)) for row in result]       
   
        for val in items:   
            timestamp = int(val['timestamp'] / 1000) 
            readable = datetime.fromtimestamp(timestamp).isoformat()
            for res in response:
                index = response.index(res)
                sectorInt = int(res['data']['sector_id'])
                if sectorInt == val['cluster_id']:
                    response[index]['data']['density'] = val['density']
                    response[index]['data']['timestamp'] = timestamp
                    response[index]['data']['date'] = readable
                    response[index]['data']['url'] = root + "sector/" + str(val['cluster_id'])
        return response

#Class for historical data of specific cluster
class History(Resource):
    def options(self, sector_id):
        return '', 204, {'Allow': 'GET, OPTIONS'}
    def get(self, sector_id):   
        args = parser.parse_args()
        response = {
            "data": {
                "sector_id": sector_id
            },
            "pagination": {},
            "metadata": {}
        }
        root = str(request.url_root)
        if args['page']:
            page = int(args['page'])
        else:
            page = 1
        
        pageLimit = 20
        offset = ((page - 1) * pageLimit)
        response['data']['entries'] = []

        if args['limit']:
            limit = str(args['limit'])    
        else:
            limit = '100'

        limitUrl = '&limit=' + limit
        #MAX AMOUNT OF FULL PAGES
        fullPageNo = math.floor(int(limit) / pageLimit)  
        #REMAINING ENTRIES ON NON FULL PAGE
        entriesModulo = int(limit) % pageLimit

        nextPage = page + 1
        
        if args['start']:
            start = str(args['start'] * 1000)
            startUrl = '&start=' + str(args['start'])
        else:
            start = '0'
            startUrl = ''

        if args['end']:
            end = str(args['end'] * 1000)
            endUrl = '&end=' + str(args['end'])
        else:
            end = int(time.time()) * 1000
            end = str(end)
            endUrl = ''

        if args['interval']:
            interval = str(args['interval'] * 1000)
            intervalUrl = '&interval=' + str(args['interval'])
        else:
            interval = str(180 * 1000)
            intervalUrl = ''

        if page == (fullPageNo + 1):
            queryLimit = entriesModulo
        elif page > (fullPageNo + 1):
            queryLimit = 0
        else:
            queryLimit = pageLimit

        result = dbQuery("SELECT timestamp, density, AVG(density) AS average FROM entry WHERE cluster_id = " + sector_id + " AND timestamp > " + start + "  AND timestamp < " + end + " GROUP BY ROUND(timestamp / " + interval + ") ORDER BY timestamp DESC LIMIT " + str(queryLimit) + " OFFSET " + str(offset))
        if len(result) <= 0:
            abort(404, message="No results found for sector {} with given parameters".format(sector_id))
        
        items = [dict(zip([key[0] for key in cur.description], row)) for row in result]
        for val in items:
            timestamp = int(val['timestamp'] / 1000) 
            readable = datetime.fromtimestamp(timestamp).isoformat()
            response['data']['entries'].append({
                'density': val['density'],
                'average_density': val['average'],
                'timestamp': timestamp,
                'date': readable
            })            
        nextPageUrl = root + "history/" + str(sector_id) + "?page=" + str(nextPage) + startUrl + endUrl + intervalUrl + limitUrl
        if page * pageLimit < int(limit):
            response['pagination']['next_url'] = nextPageUrl        
        return response

# Add resources to the API
api.add_resource(Sector, '/sector/<sector_id>')
api.add_resource(Sectors, '/sectors')
api.add_resource(History, '/history/<sector_id>')

if __name__ == '__main__':
    app.run(debug=True)