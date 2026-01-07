const axios = require('axios');
const config = require('./config.cjs');

async function debugXML() {
  const url = 'https://www.sec.gov/Archives/edgar/data/1067983/000119312525282901/46994.xml';

  try {
    const response = await axios.get(url, {
      headers: {
        'User-Agent': config.sec.userAgent
      }
    });

    const xmlContent = response.data;

    // Find first infoTable entry
    const firstEntry = xmlContent.substring(
      xmlContent.indexOf('<infoTable>'),
      xmlContent.indexOf('</infoTable>') + 12
    );

    console.log('First infoTable entry:');
    console.log(firstEntry);
    console.log('\n');

    // Find American Express entry
    const amexStart = xmlContent.indexOf('AMERICAN EXPRESS');
    if (amexStart > -1) {
      const contextStart = xmlContent.lastIndexOf('<infoTable>', amexStart);
      const contextEnd = xmlContent.indexOf('</infoTable>', amexStart) + 12;
      const amexEntry = xmlContent.substring(contextStart, contextEnd);

      console.log('American Express entry:');
      console.log(amexEntry);
    }

  } catch (error) {
    console.error('Error:', error.message);
  }
}

debugXML();
