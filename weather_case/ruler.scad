module ruler(h = 100) {
  color("white")
  cube([h, 1, 10]);
  for (x = [0:h]) {
    hihi = (x % 10 == 0) ? 10 : 5;
    if (x % 10 == 0) {
      hihi = 1;
    } else {
      hihi = 2;
      //echo(asdf=x%10);
    }
    //echo(asdad=hihi);
          color("black")
    translate([x, -0.1, 0]) {

    cube([0.1, 1.2, hihi]);
      if (x % 10 == 0) {
        translate([-0.5, 0.5, 8])
        rotate([90, 0, 0])
    text(str(x), size=1);
      }
    }
  }
}

ruler(100);