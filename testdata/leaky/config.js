// Corpus de teste: TODO segredo aqui e inventado, mas o FORMATO e o mesmo
// dos vazamentos reais encontrados nos repositorios juninmd.
// Cada linha marcada com LEAK: <rule-id> tem que ser detectada.

module.exports = {
  staging: {
    // LEAK: juninmd-hardcoded-password
    // LEAK: juninmd-aws-rds-endpoint
    host: 'fakeapp-staging.ab12cd34ef56.us-east-1.rds.amazonaws.com',
    user: 'fakeuser',
    password: 'K7#mQ2vX9pL4nR8tW3zY6bH1jF5sD0gA',
    port: 3306,
  },

  legacy: {
    // LEAK: juninmd-oracle-connect-string
    // LEAK: juninmd-internal-hostname
    connectString: 'dbpkg.empresafake.intranet:1578/PRODDB',
    user: 'usr_fake1',
    // LEAK: juninmd-hardcoded-password
    password: '!usr_fake1!',
  },

  // LEAK: juninmd-db-uri-credentials
  queue: 'amqp://fakeuser:Zx8kQ1mN4pR7@rabbit.example.com:5672',

  // LEAK: juninmd-authorization-header
  auth: 'Bearer ZDE3ZjkzMGI5NjU4MWUzOThjYWMwZTMyZWMxMjRjZmE=',
};
