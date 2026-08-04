// Corpus de teste: NADA aqui pode ser detectado.
// Sao os falsos positivos que a config precisa segurar — a maioria veio de
// varreduras que erraram antes das allowlists existirem.

module.exports = {
  // senha vem do ambiente
  password: process.env.MYSQL_PASSWORD,
  dbPassword: '${DB_PASSWORD}',
  legacyPassword: '<your-password>',
  winPassword: '%DB_PASSWORD%',

  // placeholders de documentacao
  examplePassword: 'changeme',
  docPassword: 'your-password-here',
  maskedPassword: '******',

  // banco local
  devConnectString: 'localhost:1521/XE',
  devUri: 'postgres://postgres:postgres@localhost:5432/dev',

  // nomes de arquivo que já geraram falso positivo de "host interno"
  envFiles: ['.env.local', '.env.development.local', '.env.production.local'],

  // DNS interno de Kubernetes, nao e vazamento
  broker: 'blackbox-exporter.monitoring.svc.cluster.local:9115',

  // campo de formulario chamado "local" — nao e hostname
  form: { local: 'Franca-SP' },

  // header sem token real
  authTemplate: 'Bearer <YOUR_TOKEN>',
};
