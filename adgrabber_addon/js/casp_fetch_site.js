var casper = require('casper').create();
var system = require('system');
var fs = require('fs');

var url = casper.cli.get(0); 
var output_file = casper.cli.get(1);
casper.userAgent('Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML,like Gecko) Chrome/29.0.1547.2 Safari/537.36');
casper.start('http://www.google.com/ads/preferences');
casper.thenEvaluate(function() {
  document.querySelector('form[class="ru"]').submit();
});
casper.thenOpen(url, function(){
  console.log('loading ' + url);
  this.wait(8000);
});
casper.thenOpen('http://www.google.com/ads/preferences', function(){
  this.waitForSelector("#gbmmb",function(){console.log("Casp: Managed to load google apm");},
      function(){console.log("Casp: did not load google apm");}, 5000);
  var p = this.evaluate(function() {
    return document.body.innerHTML;
  });
  fs.write(output_file + '_goog.txt',p,'w');
});

casper.thenOpen('http://bluekai.com/registry', function(){
//  this.waitForSelector(".headerText",function(){console.log("Casp: Managed to load bluekai registry");}, 
//      function(){console.log("Casp: did not load bluekai reg" );}, 5000);
  this.wait(5000);
  var p = this.evaluate(function() {
    return document.body.innerHTML;
  });
  fs.write(output_file + '_bluekai.txt',p,'w');
});

casper.run();
