$fn = 40;
board_height = 1.7;
board_width = 27.7;
hole_diameter = 2;
hole_big = 3;

size = [board_width, 4, 2];
top_bar = [31, size.y, hole_big + 2];
offset = [1, 1];

// 2 - board size
long_bolt_length = 2 + 10;
offset_big = [1.7, 1.3, ];

// latchalike?





module bolt(length = 3, diameter = 2.9) {
  d2 = diameter - 0.5;
  offset = 0.4;
  cylinder(h = length - offset, d = diameter);
  translate([0, 0, length])
  {
    translate([0, 0, -offset])
    cylinder(h = 2 + offset, d = diameter);
    
    translate([0, 0, 2])
    cylinder(h = 2, d = diameter);
  }
}

module holder(length = 3, diameter = 3) {
  d2 = diameter - 0.5;
translate([0,0,1]) {
translate([12.3,0,0])
cube([2, 1, 2], center = true);
translate([10, 0, 0])
difference() {
  cylinder(h = 2, d = diameter+2, center = true);
  cylinder(h = 10, d = d2, center = true);
  translate([-diameter, 0, 0])
  cylinder(h = 10, d = diameter*2, center=true, $fn=1);
}
}
}



// not requried, just for debug
//color("green", 0.4)
//translate([0, -3, 5])
//cube(size);

module pin(h = 1, hole_diameter=hole_diameter) {
  
translate([hole_diameter/2, hole_diameter/2, 0])
cylinder(h = h, d = hole_diameter);
}
pin_height = board_height + 2;
if (1) {
  translate([0, 0, 7])
  rotate([180, 0, 0])
  translate([0, 0, size.z]) {
    
  translate([offset.x, offset.y,0])
  mirror([0,0,1]) {
  //bolt(length = pin_height, diameter = hole_diameter);
  pin(h = pin_height);
  }
  translate([25-hole_diameter+0.8, 0, 0])
  translate([offset.x, offset.y,0])
  mirror([0,0,1]) {
  //bolt(length = pin_height, diameter = hole_diameter);
  pin(h = pin_height);
  }
  
  //translate([board_width - offset.x, offset.y, 0])
  //translate([-hole_diameter, 0, 0])
  //translate([offset.x, offset.y, 0])
  //mirror([0,0,1])
 // {
 // //bolt(length = pin_height, diameter = //hole_diameter);
  //    translate([-1, -1, 0])
  //pin(h = pin_height);
  //}
  // align
  translate([(size.x - top_bar.x)/2, 0, 0]) {
    color("yellow", 0.5)
    cube(top_bar);
    
    translate([0, 0, top_bar.z - hole_big]) {
    translate([offset_big.x,0, 0])
    rotate([90, 0, 0])
    translate([hole_big/2, hole_big/2, 0])
    bolt();
    
    translate([top_bar.x - hole_big - offset.x, 0, 0])
    rotate([90, 0, 0])
    translate([hole_big/2, hole_big/2, 0])
    bolt();
    }
  }
}
}

//translate([0, 10, 0])
//holder();
//translate([27, 10, 0])
//mirror([1, 0, 0])
//holder();

//translate([14, -4, 0])
//rotate([0, 0, 90])
//holder(diameter = hole_diameter);


//translate([14, 25, 0])
//rotate([0, 0, 270])
//holder(diameter = hole_diameter);