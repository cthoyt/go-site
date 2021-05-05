////
//// WARNING:
////   Given log volume at this point, it would be useful to maybe skip this
//// script and do something like:
////    : aws s3 sync s3://go-data-product-usage-logs/current/ . --exclude "*" --include "*2020-10-*"
////    : pigz -d *.gz
////    : cat ERTRETYERTY.2020-10-* > log-current-10.txt
////    : cat log-current-10.txt | grep -v "^#" > filtered.log.txt
////   See https://github.com/geneontology/geneontology.github.io/issues/268#issuecomment-763249662 .
//// ////
////
//// Dump the contents of a CloudFront S3 log directory's GZIPed
//// objects from AWS S3 to STDOUT.
////
//// A JSON file of credentials is required like:
////
//// { "accessKeyId": "XXX", "secretAccessKey": "YYY", "region": "us-west-1" }
////
//// Example usage (cloudfront, process verbose):
////  node ./scripts/cloudfront-log-lister.js -d -f ~/local/share/secrets/bbop/aws/s3/aws-go-push.json -b go-data-product-usage-logs/snapshot
//// Example usage (cloudfront, quiet, filtering out log comments):
////  node ./scripts/cloudfront-log-lister.js -f ~/local/share/secrets/bbop/aws/s3/aws-go-push.json -b go-data-product-usage-logs/snapshot | grep -v "^#" > /tmp/filtered.log.txt
////
//// Further use easily like:
////  cat /tmp/filtered.log.txt.20171218 | grep 131.243.192.20 | cut -f 11 | sort | uniq -c | sort -n
////

var AWS = require('aws-sdk');
var us = require('underscore');
var dns = require('dns');
var querystring = require('querystring');
var zlib = require("zlib");

///
/// Helpers.
///

// Aliases.
var each = us.each;

function _ll(arg1){
    console.log(arg1);
}

var debug = false;
function _debug(arg1){
    if( debug ){
	console.log(arg1);
    }
}

// Two or one args.
function _die(m1, m2){
    if( typeof(m2) !== 'undefined' ){
	console.error('ERROR:', m1, m2);
    }else{
	console.error('ERROR:', m1);
    }
    process.exit(-1);
}

///
/// Opts.
///

var argv = require('minimist')(process.argv.slice(2));

// Add extra "debugging" messages.
debug = argv['d'] || argv['debug'];
if( debug ){
    _debug('Debugging is on.');
}else{
}

// AWS credentials from CLI.
var credential_file = argv['f'] || argv['file'];
if( ! credential_file ){
    _die('Option (f|file) is required.');
}else{
    //_ll('Will use credentials: ' + credential_file);
}
AWS.config.loadFromPath(credential_file);

// Bucket/prefix to use.
var bucket = null;
var prefix = null;
var bucket_raw = argv['b'] || argv['bucket'];
if( ! bucket_raw ){
    _die('Option (b|bucket) is required.');
}else{
    var parts = bucket_raw.split('/');
    if( ! parts ){
	_die('Not a good bucket descriptor: ' + bucket_raw);
    }else if( parts.length === 1 ){
	bucket = parts[0];
    }else{
	bucket = parts[0];
	prefix = parts[1];
    }

    _debug('Will use bucket: ' + bucket + ', with prefix: ' + prefix);
}

///
/// Main.
///

// Setup.
var s3 = new AWS.S3({params: {Bucket: bucket, Prefix: prefix}});

// What we'll do with all the keys once we have them.
function get_objects(s3dataobjs){

    each(s3dataobjs, function(s3dataobj){
	var key = s3dataobj.Key;

	// Get the objects.
	s3.getObject({Key: key}, function(err, data){
	    if( err ){
		_die(err, err.stack);
	    }else{
		_debug('In get objects loop.');

		// // Works too.
		// var s = zlib.gunzipSync(data.Body).toString();
                // console.log(s);
		zlib.gunzip(data.Body, function(err, buffer){
		    if( err ){
			// handle error
			console.log('ERR', err);
		    }else{
			_debug('On data...');
			var str = buffer.toString();
			console.log(buffer.toString());
		    }
		});
	    }
	});
    });
}

// Get /all/ the S3 bucket object keys first.
// Adapted from: https://stackoverflow.com/a/18324270.
(function(){
    var all_keys = [];
    function list_all_keys(token, cb){

	var opts = {};
	if(token){
	    opts.ContinuationToken = token;
	}

	s3.listObjectsV2(opts, function(err, data){
	    all_keys = all_keys.concat(data.Contents);

	    if(data.IsTruncated){
		_debug('Got ' + all_keys.length +
		       ' bucket keys, continuing...');
		list_all_keys(data.NextContinuationToken, cb);
	    }else{
		_debug('Completed collection with ' +
		       all_keys.length + ' keys.');
		cb();
	    }
	});
    }
    // After we have all the objects, operate on them.
    list_all_keys(null, function(){
	get_objects(all_keys);
    });
})();
