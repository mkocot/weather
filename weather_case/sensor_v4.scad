include <nodemcu.scad>
$fn=30;
wall = 3;
// enable for print, disabled to reduce flickering
with_top_lid = 1;
show_peripheral = 0;
// szerokość, głębokość, wysokość
tower_size = [40, 80, 30];

epsilon = [0.001, 0.001, 0.001];
// make it 5mm higher than requied to add front
// bumper
bat_bumper = 5;
bat = [66, 70, 25];
// outer shell is large enough to hold bat + extra bumber at
// front
bat_outer = bat + [0, 0, bat_bumper] + [wall, wall, wall]*2;
//cube(tower_size, center=true);
// outer shell
//cube(tower_size + [wall, wall, wall], center=true);


//cube([12, 2, 2]);


module tower(size) {
  outer_size = size + 2*[wall, wall, wall];
  // shell
  module shell() {
    offset = 100;
  difference() 
    {
    cube(outer_size, center=true);
    translate([0, 0, offset/2])
    cube(size + [0, 0, offset], center=true);
  }
  }

  shell();
  // dovetail mount
  mount_height = wall;
  mount_width = outer_size.x - wall;
  translate([0, 0, (outer_size.z + mount_height)/2])
  dovetail_mount([mount_width, outer_size.y, mount_height], pad=wall/2);
  
  // bottom 'reversed' dovetail
  module bottom_rail() {
  translate([outer_size.x/2, -outer_size.y/2 + wall, -outer_size.z/2])
  rotate([90, 0, 0])
  dovetail_rail([0, outer_size.z + wall, wall]);
  }
  bottom_rail();
  mirror([1, 0, 0])
  bottom_rail();
  
  
  // mounting for nodemcu
  // nodemcu_bb.x == y (rotate by -90)
  // minimalna dziura pod "od góry płytki 23"
  off = (size.y - nodemcu_bb.x)/2;
  // we need at least 23mm from bottom to board top
  minimalDistance = (23 - nodemcu_board.z - pins.z);
  offz = (size.z - nodemcu_bb.z)/2 - minimalDistance;
  pilarHeight = minimalDistance + pins.z;
  echo(x=nodemcu_bb);
  translate([0, off - wall - 15, -offz]) {
    
    translate([0, 0, -pilarHeight/2]) {
      pilarWidth = 5;
      aboveBoard = nodemcu_board.z + 6;
      // now move to 'corners'
      translate([(-nodemcu_bb.y + pilarWidth)/2, (nodemcu_bb.x-pilarWidth)/2, 0]) {
      cylinder(d=pilarWidth, h=pilarHeight, center=true);
                      translate([0, 0, aboveBoard])
      cylinder(d=2, h=pilarHeight, center=true);
      }
      
            translate([(nodemcu_bb.y - pilarWidth)/2, (nodemcu_bb.x-pilarWidth)/2, 0]) {
      cylinder(d=pilarWidth, h=pilarHeight, center=true);
                            translate([0, 0, aboveBoard])
      cylinder(d=2, h=pilarHeight, center=true);
            }
      
            translate([(-nodemcu_bb.y + pilarWidth)/2, (-nodemcu_bb.x+pilarWidth)/2, 0]) {
      cylinder(d=pilarWidth, h=pilarHeight, center=true);
                            translate([0, 0, aboveBoard])
      cylinder(d=2, h=pilarHeight, center=true);
            }
      
            translate([(nodemcu_bb.y - pilarWidth)/2, (-nodemcu_bb.x+pilarWidth)/2, 0]) {
      cylinder(d=pilarWidth, h=pilarHeight, center=true);
              translate([0, 0, aboveBoard])
      cylinder(d=2, h=pilarHeight, center=true);
            }
    }
  
  
    if (show_peripheral) {
    #rotate([0, 0, -90])
    nodemcu();
    }
  }
  
  // if this would 'clip' into board it's ok
  // we have possibility to move up and down
 
  
  
  // sensor mount
  // compensate +2 for wall size
  holder_size = 5+2;
  // ground floor for holders
  translate([0, 0, holder_size/2 - size.z/2]) {
    // Power cables
    translate([0, -25, 0])
    rotate([0, 0, 90])
    cable_holder([3, holder_size, holder_size]);
    
    // 1/3 rings for sensor
    translate([0, -5, 0])
    rotate([0, 0, 90]) cable_holder([3, holder_size, holder_size]);
    //2/3
    translate([10, 5, 0])
        rotate([0, 0, -45]) cable_holder([3, holder_size, holder_size]);
  }
  // and now sensor 'slide in'
  // TODO(m): hole dimension
  holder_height = 15;
  translate([0, 22, (holder_height - size.z)/2])
  rotate([0, 90, 0]) {
    difference() 
    {
  // 2mm for 2x wall 3 for real hole size
  cable_holder([holder_height, 18, 2+3], wall=1);
      color("green")
      translate([0, 6.5, -2])
      cube([holder_height+1, 3, 2], center=true);
      color("green")
      translate([0, -8.5, 0])
      cube([holder_height+1, 2, 3], center=true);
    //translate([0, -4, -3.5])
   //color("green")
  //cable_holder([holder_height+2, 16, 3.5*2+3], wall=3.5);
    }
  }
}

// dovetail mount
module dovetail_rail(size) {
    width = size.x;
    height = size.z;
    difference() {
      cube([height, size.y, height]);
      translate([0, -0.005, 0])
      rotate([0, 45, 0]) cube([height + 0.1, size.y + 0.01, 100]);
    }
}

module dovetail_lid(size, holes=false) {
  unit = [size.x, size.z]/2;
  points = [
  [-unit.x, -unit.y],
  [-unit.x + unit.y*2, unit.y],
  [unit.x - unit.y*2, unit.y],
  [unit.x, -unit.y]
  ];
    hole = 5;
  module hole_solid() {
    hole_width = size.x-2-3*hole;
  linear_extrude(size.z*2)
   translate([-size.x/2 +1+ 1.5*hole, 0, 0])
  hull() {
  circle(d=hole);
    translate([hole_width, 0, 0])
  circle(d=hole);
  }
}

 difference() {
  translate([0, size.y/2, 0])
  rotate([90, 0, 0])
  linear_extrude(size.y)
  polygon(points);
  

  if (holes) {

    sections = floor(size.y/hole/2);
    echo(sections=sections);
    for (i = [0:sections-1]) {
      translate([0, hole-sections*hole + i*(hole*2), -size.z])
    color("red")
    hole_solid();
    }
  }
}
}

module dovetail_mount(size, pad=0) {
  if (with_top_lid) {
  difference() {
    cube(size, center=true);
    scale([1.001, 1.001, 1.001]) dovetail_lid(size);
    // reduce flickering on bottom
    //translate([0, 0, -size.z+1])
    //cube(size, center=true);
    // reduce flickering on top
    //translate([0, 0, size.z-1])
    //cube(size - [wall*2, 0, 0], center=true);
  }
}
  module padding() {
    translate([-size.x/2 - pad/2,  0, 0])
    cube([pad, size.y, size.z], center=true);
  }
  padding();
  mirror([1, 0, 0])
  padding();
}

module battery() {
  // add square mount
  pad = wall;
  dove_size = [tower_size.x + wall*4+1,
  tower_size.z + 15,
  wall  ];
  dove_size_with_pad = dove_size + [pad*2, 0, 0];
  back_stop_size = [dove_size_with_pad.x + 1, dove_size.z, wall*2];
    // push back by 9mm to ensure our lid will not cross battery
  extend = 9;
  plus = 10;
  
module base() {

  translate([0, bat_outer.y/2 - dove_size.y/2, -bat_outer.z/2  - wall/2]) {
    color("purple") hull()
    translate([0, -dove_size.y/2, +wall/2-back_stop_size.z/2]) {
      cube(back_stop_size, center=true);
      translate([0, -4, 3.5])
      cube([back_stop_size.x, back_stop_size.y, 0.1], center=true);
    }
    rotate([180, 0, 0]) dovetail_mount(dove_size, pad=pad);
  }


  difference() {
  color("red")
  translate([0, -extend/2, 0])
  cube(bat_outer + [0, extend, 0], center=true);
    
  translate([0, -extend/2 + plus/2, 0])
  color("blue")
  cube(bat + [0, extend + plus, bat_bumper], center=true);
  }
  
  bumber_width = bat_bumper*1.8;
  slope_start = 3;
  hull()
  translate([0, bat_outer.y/2 - bumber_width/2 , bat.z/2]){
    translate([0, slope_start/2, 0])
    cube([bat.x, bumber_width-slope_start, bat_bumper], center=true);
    translate([0, -2, bat_bumper/2 + 0.1])
    cube([bat.x, bumber_width, 0.1], center=true);
  }
  
  // virtual battery (disable for print)
  if (show_peripheral) {
  #translate([0, -extend, 0])
  cube(bat, center=true);
  }
}

  
  module bottom_holes(from=0, to=5) {
  // punch holes
  // .    .
  // .    .
  bottom_size = bat.x - wall*2;
  hole_d = wall*2;
  front_size = 0;
    translate([0, 0, 10])
    linear_extrude(10)
  translate([0, -extend - 5, 0]) {
    translate([-bottom_size/2, bat.y/2, 0]){
      for (y = [from:to]) {
        translate([0, -11*y, 0])
        hull() {
          circle(d = hole_d);
          translate([bottom_size/2 - wall*2, 0, 0])
            circle(d = wall*2);
        }
      }
    }
  }
}

module side_holes() {
  bottom_size = bat.z+wall*2;
  hole_d = wall*2;
  front_size = 0;

translate([bat.x/2 - wall, 0, -bat.z/2+wall/2])
     rotate([0, 90, 0]) linear_extrude(10)
  translate([0, -extend - 5, 0]) {
    translate([-bottom_size/2, bat.y/2, 0]){
      for (y = [0:5]) {
        translate([0, -11*y, 0])

        hull() {
          circle(d = hole_d);
          translate([bottom_size/2 - wall*2, 0, 0])
            circle(d = wall*2);
        }
      }
    }
  }
}

// assembly
difference() {
base();
side_holes();
mirror([1, 0, 0]) side_holes();
bottom_holes();
mirror([1, 0, 0]) bottom_holes();

mirror([0, 0, 1]) {
  bottom_holes(from=4);
  mirror([1, 0, 0]) bottom_holes(from=4);
}

}
}

/* NOTE(m) For printing use SLIGHTLY smaller dovetail_lid
   to make sure it will fit into holes
*/
difference() {
  union() {
  // nodemcu + sensor mount
  tower(tower_size);
    // battery
  *translate([0, -((tower_size.y+wall*2)/2+bat_outer.z/2), -14])
  rotate([90, 0, 0]) battery();
  }
  // hole for cables
  translate([0, -tower_size.x, 0])
  cube([15, 13, 15], center=true);
  
  // lid hole
total = bat_outer.z + tower_size.y + wall*5;
color("purple")
translate([0, -total/2 + bat_outer.z+wall*6, 19.5]) 
dovetail_lid([tower_size.x + wall+1,
  total,
  0.4+wall]);
}




// lid
total = bat_outer.z + tower_size.y + wall;
*translate([100, 0, -19.5])
translate([0, 0, 19.5])
dovetail_lid([tower_size.x + wall - 0.5, total - 0.5, wall - 0.5], holes=true);
echo(asd=[tower_size.x + wall - 0.5, total - 0.5, wall - 0.5]);

module cable_holder(size, wall=1) {
  difference() {
  cube(size, center=true);
  cube(size + [wall, -wall*2, -wall*2], center=true);
  }
}

//!cable_holder([2, 5, 5]);