import os
from web_service import create_app

PORT = int(os.getenv('PORT', '80'))
app = create_app()
app.run(host='0.0.0.0', port=PORT, threaded=True)
