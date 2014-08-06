var casper = require('casper').create({
//    verbose : true,
//    logLevel : "debug",
//    pageSettings : {
//        loadPlugins : true
//    },
//   clientScripts: ["includes/jquery-2.0.3.min.js"]
});
casper.userAgent('Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML,like Gecko) Chrome/29.0.1547.2 Safari/537.36');
var sys = require('system');
var fs = require('fs');
var url = casper.cli.get(0);
var worker_id = casper.cli.get(1);
var refresh = casper.cli.get(2) || 1; 
var refresh_num = [];
var framesContent = [];
for (var i=0; i < refresh; i++){
  refresh_num.push(i);
}
casper.start();
casper.then(function(){
    this.eachThen(refresh_num, function(response){
        this.thenOpen(url, function () {
            var har;
            var frameNum = 0;
            var currentPath = [];
            this.wait(7000,function(){
                try{
                    var framecontent = this.evaluate(function() {
                        function getImgSrc(frameObj){
                            imgs = frameObj.querySelectorAll('img');
                            var imgSrc = [];
                            for (var i=0; i < imgs.length; i++){
                                imgSrc.push(imgs[i].src);
                            }
                            return imgSrc;
                        }
                        var framesource = getImgSrc(document.body);
                        var framestack = [];
                        var frames = document.querySelectorAll("iframe");
                        for (var i=0; i<frames.length; i++){
                            framestack.push(frames[i]);
                        }                 
                        while (framestack.length > 0){
                            var nextFrame = framestack.pop();
                            framesource = framesource.concat(getImgSrc(nextFrame.contentDocument));
                            var newFrames = nextFrame.contentDocument.querySelectorAll("iframe");
                            for(var i=0; i < newFrames.length; i++){
                                framestack.push(newFrames[i]);
                            }
                        }
                        return framesource;
                    });

                    framesContent.push(framecontent);
                }catch(e){
                    console.log(e);
                }
//                this.capture('Afterwaiting.png');
            });
        });
    });
});
casper.then(function(){
    var fpath = 'phantomDir/img_' + worker_id + '.txt'; 
    fs.write(fpath, JSON.stringify(framesContent, undefined, 4), 'w');
});
casper.run();


