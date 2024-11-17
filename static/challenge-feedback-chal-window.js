String.prototype.format = function () {
    const args = arguments;
    return this.replace(/{([0-9]+)}/g, function (match, index) {
        return typeof args[index] == 'undefined' ? match : args[index];
    });
};

const FEEDBACK_TYPES = {
    RATING: 0,
    TEXT: 1
}

document.addEventListener('DOMContentLoaded', function() {
    var feedbackInlineForm = `<div id="chal-feedback-group">
      <br>
      <h4 class="text-center pb-1">Give Feedback</h4>
      
      <form id="chal-feedback-form" method="POST" action="/chal/{0}/feedbacks/answer" class="form-horizontal max-500px center bg-form bg-form--no-bg">
        <input id="nonce" name="nonce" type="hidden" value="{1}">
        
        <div id="input-fields"></div>
        
        <div class="row">
            <div class="col-6 pe-0">
                <div id="feedback-result-notification" class="alert alert-success alert-dismissable text-center w-100 mb-0 h-100" role="alert" style="display: none;">
                    <strong id="feedback-result-message"></strong>
                </div>
            </div>
            <div class="col-6">
                <button id="feedback-submit-button" class="btn btn-primary btn-block flex-column" name="_submit" type="submit" value="Submit">Submit</button>
            </div>
        </div>
      </form>
    </div>`;


    var chalid = -1;
    var visibleFeedbackForm = null;

    // Show feedback form when challenge window is shown
    document.getElementById('challenge-window').addEventListener('shown.bs.modal', function (event) {
        chalid = document.querySelector("#challenge-window [x-init^='id =']").getAttribute('x-init').split('=')[1].trim();
        visibleFeedbackForm = null;
        showFeedbackForm(false);
    });

    // Show feedback form when challenge is submitted
    document.addEventListener("click", function(event) {
        if (event.target.id === "challenge-submit") {
            const observer = new MutationObserver((mutations) => {
                const alertElement = document.querySelector(".alert");
                if (alertElement) {
                    showFeedbackForm(true);
                    observer.disconnect();
                }
            });

            const targetNode = document.querySelector(".notification-row");
            if (targetNode) {
                observer.observe(targetNode, { childList: true, subtree: true });
            }
        }
    });

    function showFeedbackForm(isScrollTo = false) {
        if (visibleFeedbackForm != null) {
            return;
        }

        fetch(CTFd.config.urlRoot +`/chal/${chalid}/feedbacks`)
        .then(response => response.json())
        .then(data => {

            if (!data.feedbacks || data.feedbacks.length <= 0) {
                return;
            }

            var res = feedbackInlineForm.format(chalid, CTFd.config.csrfNonce);

            var obj = CTFd.lib.$(res);
            visibleFeedbackForm = obj;

            var inputFields = obj.find("#input-fields");

            for (var i = 0; i < data.feedbacks.length; i++) {
                const feedback = data.feedbacks[i];

                const formgroup = document.createElement("div");
                formgroup.className = "mb-3";

                const b = document.createElement("b");
                let label;

                switch(feedback.type) {
                    case FEEDBACK_TYPES.RATING:
                        label = document.createElement("label");
                        label.setAttribute("for", "feedback-" + feedback.id);
                        label.innerHTML = feedback.question;

                        let select = document.createElement("select");
                        select.id = "feedback-" + feedback.id;
                        select.name = "feedback-" + feedback.id;
                        select.className = "form-control form-select form-select--reset";

                        let ratingLowLabel = "";
                        let ratingHighLabel = "";
                        if (feedback.extraarg1 !== "") {
                            ratingLowLabel = " - " + feedback.extraarg1;
                        }
                        if (feedback.extraarg2 !== "") {
                            ratingHighLabel = " - " + feedback.extraarg2;
                        }

                        let option = document.createElement("option");
                        option.value = 1;
                        option.innerHTML = "1" + ratingLowLabel;
                        select.appendChild(option);
                        for (let optioni = 2; optioni <= 4; optioni++) {
                            option = document.createElement("option");
                            option.value = optioni;
                            option.innerHTML = optioni;
                            select.appendChild(option);
                        }

                        let option5 = document.createElement("option");
                        option5.value = 5;
                        option5.innerHTML = "5" + ratingHighLabel;
                        select.appendChild(option5);

                        if (feedback.answer !== "") {
                            select.value = feedback.answer;
                        }

                        b.append(label);
                        formgroup.append(b);
                        formgroup.append(select);
                        break;

                    case FEEDBACK_TYPES.TEXT:
                        label = document.createElement("label");
                        label.setAttribute("for", "feedback-" + feedback.id);
                        label.innerHTML = feedback.question;

                        let input = document.createElement("input");
                        input.type = "text";
                        input.id = "feedback-" + feedback.id;
                        input.name = "feedback-" + feedback.id;
                        input.className = "form-control";
                        input.pattern = ".{1,}";
                        input.value = feedback.answer;
                        input.required = true;

                        b.append(label);
                        formgroup.append(b);
                        formgroup.append(input);
                        break;
                }
                inputFields.append(formgroup);
            }

            obj.find("#feedback-submit-button").get(0).addEventListener("click", function(e) {
                e.preventDefault();
                e.stopPropagation();
                var submitButton = CTFd.lib.$(this);
                submitButton.addClass("disabled-button");
                submitButton.prop('disabled', true);

                fetch(CTFd.config.urlRoot + '/chal/' + chalid + '/feedbacks/answer',
                    {
                        method: "POST",
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                        body: new URLSearchParams(new FormData(obj.find("#chal-feedback-form").get(0)))
                        // data: obj.find("#chal-feedback-form").serialize(),
                    })
                    .then(response => response.json())
                    .then(result => {
                        var result_message = obj.find('#feedback-result-message');
                        var result_notification = obj.find('#feedback-result-notification');
                        result_message.text(result.message);
                        result_notification.show();


                        setTimeout(function () {
                            CTFd.lib.$('.alert').hide();
                            submitButton.removeClass("disabled-button");
                            submitButton.prop('disabled', false);
                        }, 3000);
                    })
                    .catch((error) => {
                        console.error('Error:', error);
                    });
                });
            
            CTFd.lib.$("#challenge").append(obj);
            // Scroll to the feedback form
            document.getElementById('chal-feedback-group').scrollIntoView({behavior: "smooth", block: "end"});
        });
    }

});