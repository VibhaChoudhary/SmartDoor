$(document).ready(function() {
    function getParam(visitor){
       return sdk.visitorKeyGet(
           {'key': visitor},
           {},
           {});
    }
    function postVisitor(visitor, n, p){
        return sdk.visitorKeyPost(
            {'key': visitor},
            {name : n, phone: p},
            {}
        );
    }
    function callgetParams(){
        const urlParams = new URLSearchParams(window.location.search);
        if(urlParams.has('visitor')){
            const visitor = urlParams.get('visitor');
            getParam(visitor).
            then((response) => {
                    console.log("Response", response);
                    let src = "data:image/png;base64," + response['data']['image'];
                    $("#photo").attr("src", src).height(250).width(260);
            })
            .catch((error) => {
                console.log('an error occurred while getting visitor', error);
            });
        }
    }
    function showNotification(){
        $('.v-details').hide();
        $('.action').hide();
        $('.notify').show();
    }

    callgetParams();

    $('.v-approve').on('click', function() {
        $('.v-details').show();
    });
    $('.v-deny').on('click', function() {
        $('.v-details').hide();
        const urlParams = new URLSearchParams(window.location.search);
        if(urlParams.has('visitor')) {
            const visitor = urlParams.get('visitor');
            postVisitor(visitor, '', '').then((response)=>{
                console.log("Response", response);
            }).catch((error)=>{
                console.log('an error occurred while denying visitor entry', error);
            });
        }
        showNotification();
    });
    $('.submit').on('click', function() {
        const name = $('.v-name').val();
        const phone = $('.v-phone').val();
        if ($.trim(name) === '' || $.trim(phone) === '') {
            return false;
        }
        const urlParams = new URLSearchParams(window.location.search);
        if(urlParams.has('visitor')) {
            const visitor = urlParams.get('visitor');
            postVisitor(visitor, name, phone).then((response)=>{
                console.log("Response", response);
            }).catch((error)=>{
                console.log('an error occurred while allowing visitor entry', error);
            });
        }
        showNotification();
    });



});
