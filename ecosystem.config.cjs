module.exports = {
  apps: [
    {
      name: 'bot-options',
      script: 'src/main.py',
      interpreter: 'python3.12',
      cwd: '/home/deploy-app/bot-options',
      env: {
        PYTHONUNBUFFERED: '1'
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      max_memory_restart: '500M',
      restart_delay: 10000,
      max_restarts: 5
    },
    {
      name: 'options-dashboard',
      script: 'src/dashboard.py',
      interpreter: 'python3.12',
      cwd: '/home/deploy-app/bot-options',
      env: {
        PYTHONUNBUFFERED: '1',
        DASHBOARD_PORT: '3001'
      }
    }
  ]
};
