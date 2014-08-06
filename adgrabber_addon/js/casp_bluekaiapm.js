var casper = require('casper').create();
var fs = require('fs');
var url = casper.cli.get(0); 
var output_file = casper.cli.get(1);
casper.userAgent('Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML,like Gecko) Chrome/29.0.1547.2 Safari/537.36');
casper.start(url, function(){
  console.log('loading ' + url);
  this.wait(10000);
  this.capture('url.png');
  var p = this.evaluate(function() {
    return document.body.innerHTML;
  });
  fs.write('urlps.txt', p,'w');
});
casper.thenOpen('http://bluekai.com/registry', function(){
  this.wait(15000);
  this.capture('bluekai_1.png');
  
  this.waitForSelector(".headerText",function(){console.log("detectedinterest");}, 
                       function(){console.log("didnot detect");}, 5000);
  var p = this.evaluate(function() {
    return document.body.innerHTML;
  });
  this.capture('bluekai.png');
  fs.write(output_file,p,'w');
});

casper.run();
