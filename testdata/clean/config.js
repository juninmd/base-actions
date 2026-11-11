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

  // forward do AMX Mod X: prefixo fw_ igual ao da Fireworks, mas e nome de funcao
  amxForward: 'fw_PlayerPreThinkPostHookHandler',

  // endpoints de metadados de cloud: hostnames publicos e fixos
  metadata: 'http://metadata.google.internal/computeMetadata/v1/',
  linkLocal: 'http://169.254.169.254/latest/meta-data/',

  // dominios reservados para documentacao/teste (RFC 2606)
  exampleHost: 'interno.example.corp',
  docHost: 'api.servico.example.com',

  // campo de formulario chamado "local" — nao e hostname
  form: { local: 'Franca-SP' },

  // token lido do ambiente (env injetado / Bun.env), nao e literal
  mcp: { token: env.MY_ACADEMY_TOKEN || '' },
  bun: { token: Bun.env.SERVICE_ACCESS_TOKEN || '' },

  // header sem token real
  authTemplate: 'Bearer <YOUR_TOKEN>',

  // placeholders dos formatos novos de API key
  geminiPlaceholder: 'AQ.Ab<your-key-here>',
  openRouterPlaceholder: 'sk-or-v1-<your-key-here>',
  groqPlaceholder: 'gsk_<your-key-here>',
  xaiPlaceholder: 'xai-<your-key-here>',
  googleClientSecretPlaceholder: 'GOCSPX-<your-client-secret>',

  // placeholders dos formatos incorporados do tokenix/TruffleHog
  awsSecretPlaceholder: 'aws_secret_access_key = "changeme"',
  azureStoragePlaceholder: 'AccountKey=changeme==',
  stripeWebhookPlaceholder: 'whsec_changeme',
  datadogPlaceholder: 'ddog_changeme',
  supabasePlaceholder: 'sbp_changeme',
  sentryDsnPlaceholder: 'https://<key>@example.com/0',
};
