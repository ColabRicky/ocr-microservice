const fs = require('fs');
const base64Data = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
fs.writeFileSync('/Users/rickyho/Documents/github/ocr-microservice/test.png', Buffer.from(base64Data, 'base64'));
console.log('Test image generated successfully.');
