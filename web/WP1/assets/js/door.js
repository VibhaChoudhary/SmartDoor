$(document).ready(function() {
    function getKinesisStream() {
        var protocol = 'HLS';
        var streamName = 'VirtualDoorStream';

        // Step 1: Configure SDK Clients
        var options = {
            accessKeyId: '',
            secretAccessKey: '',
            sessionToken: '',
            region: 'us-east-1',
        }
        var kinesisVideo = new AWS.KinesisVideo(options);
        var kinesisVideoArchivedContent = new AWS.KinesisVideoArchivedMedia(options);

        // Step 2: Get a data endpoint for the stream
        console.log('Fetching data endpoint');
        kinesisVideo.getDataEndpoint({
            StreamName: streamName,
            APIName: protocol === 'DASH' ? "GET_DASH_STREAMING_SESSION_URL" : "GET_HLS_STREAMING_SESSION_URL"
        }, function (err, response) {
            if (err) {
                return console.error(err);
            }
            console.log('Data endpoint: ' + response.DataEndpoint);
            kinesisVideoArchivedContent.endpoint = new AWS.Endpoint(response.DataEndpoint);

            // Step 3: Get a Streaming Session URL
            var consoleInfo = 'Fetching ' + protocol + ' Streaming Session URL';
            console.log(consoleInfo);

            kinesisVideoArchivedContent.getHLSStreamingSessionURL({
                StreamName: streamName,
                PlaybackMode: "LIVE",
                HLSFragmentSelector: {
                    FragmentSelectorType: 'SERVER_TIMESTAMP',
                    TimestampRange: undefined
                },
                // ContainerFormat: $('#containerFormat').val(),
                // DiscontinuityMode: $('#discontinuityMode').val(),
                // DisplayFragmentTimestamp: $('#displayFragmentTimestamp').val(),
                // MaxMediaPlaylistFragmentResults: parseInt($('#maxResults').val()),
                Expires: parseInt(60 * 60)
            }, function (err, response) {
                if (err) {
                    return console.error(err);
                }
                console.log('HLS Streaming Session URL: ' + response.HLSStreamingSessionURL);

                var playerElement = $('#vid');
                playerElement.show();
                var player = new Hls();
                console.log('Created HLS.js Player');
                player.loadSource(response.HLSStreamingSessionURL);
                player.attachMedia(playerElement[0]);
                console.log('Set player source');
                player.on(Hls.Events.MANIFEST_PARSED, function () {
                    video.play();
                    console.log('Starting playback');
                });
            });
        });
    }

    function setDoorDimension(){
        var newWidth = $(".door-container").width();
        var newHeight = $(".door-container").height();
        $('.door').width(newWidth);
        $('.door').height(newHeight);
        $('.door-left img').height(newHeight);
        $('.door-right img').height(newHeight);
        $('.door-left img').width(newWidth/2);
        $('.door-right img').width(newWidth/2);
    }

    function openDoor(name){
        console.log(name)
        $('.video-container').hide();
        $('.otp-container').hide();
        $('.door-left').css({
            'transform-origin': '0% 0%',
            'animation':'open 1s linear',
            'animation-fill-mode': 'forwards'
        });
        $('.door-right').css({
            'transform-origin': '100% 0%',
            'animation':'open2 1s linear',
            'animation-fill-mode': 'forwards'
        });
        let msg = 'Welcome ' + name + "!";
        $('.notify p').text(msg);
        $('.notify').show();
    }

    function matchOtp(otp){
        validateOTP(otp).then((response) => {
            console.log(response);
            status = response['data']['status'];
            if(status === 'true'){
                let name = response['data']['name'];
                console.log("name is", name);
                if(name){
                    openDoor(name);
                }
            } else {
                $('.otp-container').hide();
                $('.notify p').text("Sorry, the system couldn't recognise your face!");
                $('.notify').show();
            }
            streamProcessor('stop_and_expire', otp).then((response) => {
                console.log(response);
            }).catch((error) => {
                console.log('an error occurred while stopping stream', error);
            });
        }).catch((error) => {
            console.log('error occurred while validating otp');
        });
    }

    function streamProcessor(action, passcode = ''){
        return sdk.streamPost({},
            {
                action : action,
                otp : passcode
            },
            {});
    }

    function validateOTP(otp) {
        return sdk.passcodePost({},
            {
                "otp" : otp
            }, {});
    }

    setDoorDimension();

    $('.otp-submit').on('click', function() {
        val = $('.otp-input').val();
        if ($.trim(val) == '') {
            return false;
        }
        $('.otp-input').val(null);
        matchOtp(val);
    });

    $('.entry-button').on('click', function() {
        getKinesisStream();
        $('.video-container').show();

        streamProcessor('start').then((response) => {
            console.log(response);
        }).catch((error) => {
            console.log('an error occurred while starting stream', error);
        });
        $('.otp-container').show();
        $('.entry-button').hide();
        $('.exit-button').show();
    });

    $('.exit-button').on('click', function() {
        streamProcessor('stop').then((response) => {
            console.log(response);
        }).catch((error) => {
            console.log('an error occurred while stopping stream', error);
        });
        $('.otp-container').hide();
        $('.video-container').hide();

        $('.exit-button').hide();
        $('.entry-button').show();
        $('.notify').hide();
        $('.door-left').css({
            'transform-origin': '',
            'animation':'',
            'animation-fill-mode': ''
        });
        $('.door-right').css({
            'transform-origin': '',
            'animation':'',
            'animation-fill-mode': ''
        });
    });
});
