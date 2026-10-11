"""Independent protocol histories; isolated process, temporary database, ephemeral HTTP."""
import concurrent.futures
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from base import Problem, handler
from service import Service

class Review(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.database=Path(self.temp.name)/'state.sqlite'
  self.now=[1_000_000];self.a=Service(self.database,clock=lambda:self.now[0]);self.b=Service(self.database,clock=lambda:self.now[0]);self.servers=[]
 def tearDown(self):
  for server,thread in self.servers:server.shutdown();server.server_close();thread.join(2)
  self.temp.cleanup()
 def body(self,action,args=None,identity=None):return {'id':identity or str(uuid.uuid4()),'action':action,'args':args or {}}
 def run_command(self,body,owner=None):return (owner or self.a).route('POST','/commands',body)[1]
 def command(self,action,args=None,owner=None):return self.run_command(self.body(action,args),owner)
 def view(self,owner=None):return (owner or self.a).route('GET','/view',{})[1]['data']
 def serve(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.a));thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True);thread.start();self.servers.append((server,thread));return server.server_port
 def http(self,port,path,body=None):
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=4)
  try:
   c.request('GET' if body is None else 'POST',path,body=None if body is None else json.dumps(body));r=c.getresponse();return r.status,json.loads(r.read())
  finally:c.close()


 def grant(self):return {k:self.view()[k] for k in ('boot','connection')}
 def connect(self):self.command('connect');return self.grant()
 def target(self,value):return self.command('set',self.grant()|{'target':value})
 def test_desired_and_reported_stay_separate_until_exact_current_ack(self):
  self.connect();self.target(22);first=self.view()['pending'];self.target(23);current=self.view()['pending']
  self.assertEqual((23,21),(self.view()['desired'],self.view()['reported']))
  self.assertFalse(self.command('ack',first)['outcome']['accepted']);self.assertEqual(21,self.view()['reported'])
  self.assertTrue(self.command('ack',current)['outcome']['accepted']);self.assertEqual((23,2),(self.view()['reported'],self.view()['acknowledged']))
 def test_wrong_target_same_sequence_does_not_set_reported_value(self):
  self.connect();self.target(22);pending=self.view()['pending'];self.assertFalse(self.command('ack',pending|{'target':23})['outcome']['accepted'])
  self.assertEqual(pending,self.view()['pending']);self.assertEqual(21,self.view()['reported'])
 def test_disconnect_reconnect_fences_previous_connection_callbacks(self):
  old=self.connect();self.target(24);ack=self.view()['pending'];self.command('disconnect',old)
  self.assertFalse(self.command('ack',ack)['outcome']['accepted']);self.connect()
  self.assertFalse(self.command('ack',ack)['outcome']['accepted']);self.assertFalse(self.command('set',old|{'target':16})['outcome']['accepted'])
  self.assertEqual((24,21),(self.view()['desired'],self.view()['reported']));self.target(24);self.command('ack',self.view()['pending']);self.assertEqual(24,self.view()['reported'])
 def test_reboot_keeps_desired_but_resets_report_and_fences_same_sequence(self):
  self.connect();self.target(25);old=self.view()['pending'];self.command('reboot');self.assertEqual((2,25,20,1),(self.view()['boot'],self.view()['desired'],self.view()['reported'],self.view()['nextSequence']))
  self.connect();self.target(25);new=self.view()['pending'];self.assertEqual(1,new['sequence'])
  self.assertFalse(self.command('ack',old)['outcome']['accepted']);self.command('ack',new);self.assertEqual(25,self.view()['reported'])
 def test_lost_set_receipt_and_old_ack_replay_do_not_revert_new_command(self):
  self.connect();body=self.body('set',self.grant()|{'target':22});port=self.serve();self.http(port,'/__control',{'drop_reply':True})
  with self.assertRaises(http.client.RemoteDisconnected):self.http(port,'/commands',body)
  self.http(port,'/__control',{});receipt=self.run_command(body,Service(self.database));self.assertEqual(1,receipt['outcome']['sequence'])
  ackbody=self.body('ack',self.view()['pending']);ack=self.run_command(ackbody);self.target(24)
  self.assertEqual(ack,self.run_command(ackbody));self.assertEqual((24,22),(self.view()['desired'],self.view()['reported']))
 def test_parallel_sets_get_distinct_monotonic_sequences_and_only_latest_ack(self):
  grant=self.connect()
  with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda pair:self.command('set',grant|{'target':pair[1]},pair[0]),[(self.a,22),(self.b,23)]))
  self.assertEqual([1,2],sorted(r['outcome']['sequence'] for r in results));self.assertEqual(3,self.view()['nextSequence'])
  for result in results:
   ack=result['data']['pending'];expected=ack['sequence']==2;self.assertEqual(expected,self.command('ack',ack)['outcome']['accepted'])
 def test_negative_old_ack_remains_rejected_after_later_state_changes(self):
  self.connect();self.target(22);old=self.view()['pending'];self.target(23);body=self.body('ack',old);receipt=self.run_command(body)
  self.command('reboot');self.assertEqual(receipt,self.run_command(body));self.assertFalse(receipt['outcome']['accepted'])
 def test_target_range_and_integer_types_prevent_mutation(self):
  self.connect();before=self.view()
  for target in (15,29,True,22.0,'22'):
   with self.assertRaises(Problem):self.target(target)
  self.assertEqual(before,self.view())

if __name__=='__main__':unittest.main()
