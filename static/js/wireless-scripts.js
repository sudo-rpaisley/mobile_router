$(document).ready(function () {
  $("#listAdapters1").on("click", function (event) {
    $.ajax({
      url: "/adapters",
      type: "POST",
      beforeSend: function () {
      },
      success: function (response) {
        console.log(response);
        // Refresh the page to show updated interface information
        location.reload();
      },
      error: function (error) {
        console.log(error);
      },
      complete: function () {
      }
    });
  });

  $("#listAdapters2").on("click", function (event) {
    $.ajax({
      url: "/adapters",
      type: "POST",
      beforeSend: function () {
      },
      success: function (response) {
        console.log("list adpters Was Successfull. YAY!!!");
        console.log(response);
        // Refresh the page so the navbar shows the latest adapters
        location.reload();
      },
      error: function (error) {
        console.log(error);
      },
      complete: function () {
      }
    });
  });
});


