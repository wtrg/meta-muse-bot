INSERT INTO emails (id, address_id, sender, "from", "to", subject, body_text, body_html, received_at) 
VALUES (
  'mail_mock_meta_01', 
  '9d00c998-f2b7-4246-9995-dc423e403436', 
  'security@meta.com', 
  'Meta Security <security@meta.com>', 
  'muse_test_01_821f@spinupmail.dev', 
  '582910 is your Meta security code', 
  'Hi Trường,\n\nYour Meta verification code is 582910. Enter this code to verify your Muse.ai account.\n\nOr click https://muse.ai/verify?token=abc123meta to verify directly.', 
  '<p>Hi Trường,</p><p>Your Meta verification code is <b>582910</b>.</p><p><a href="https://muse.ai/verify?token=abc123meta">Verify on Muse.ai</a></p>', 
  1792336600000
);
