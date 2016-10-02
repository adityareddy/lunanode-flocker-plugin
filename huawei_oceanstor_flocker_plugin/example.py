from lndynamic import LNDynamic
import socket
from uuid import UUID

api = LNDynamic(api_id, api_key)
print api.request('volume', 'attach', {'region': 'toronto', 'volume_id': '2537', 'vm_id': '082b1e6b-f22b-49de-af41-1af7492280ae', 'target': 'auto'})