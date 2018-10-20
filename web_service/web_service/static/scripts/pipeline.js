$(document).ready(function() {
  // When the page loads or the user hits back button, reset any form elements
  $(window).bind("pageshow", function() {
    $("#submit-button").button('reset');
  });

  var submitButton = document.getElementById('submit-button')
  submitButton.onclick = function() {
    var $this = $(this);
    $this.button('loading');
  }
  document.getElementById("pipeline-create-tab").className = "active"
});
