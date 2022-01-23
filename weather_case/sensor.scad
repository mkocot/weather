$fn = 10;
// size of battery module
bat = [70, 70, 25];

nodemcu_size = [30, 56];
// 2mm border (for each side)
border = 2;
// cap height
cap = [0, 20, 0];

// for debug purpose
cap_offset = 20;

module cpu_pilar(x, y) {
  color("blue")
  translate([x, y, 0])
  union() {
    cylinder(h=10, r=1, center=false);
    cylinder(h=5, r=2, center=false);
  }
}
module battery_bed() {
difference() {
      // make nice round casing
      linear_extrude(bat.z + border*2)
      offset(r = border)
      square(bat.x + border);
        
      translate([border, 0, border])
      cube(bat + [0, 100, 0]);
      // hole for power cords
      // ensure we don't clip bottom
      translate(bat - [bat.x/3, bat.y/2, 0])
      cube([5, 5, 1000]);
    }
}

module cpu_bed() {
  union() {
      // just for preview
      //square(nodemcu_size);
      // support pilars at corners
      cpu_pilar(3, 3);
      cpu_pilar(nodemcu_size.x - 3, 3);
      cpu_pilar(nodemcu_size.x - 3, nodemcu_size.y - 3);
      cpu_pilar(3, nodemcu_size.y - 3);
    }
}

module cpu_cap() {
            // cap on cpu
        difference() {
        color("purple")
        linear_extrude(cap.y)
        offset(r = border)
        square(bat.x + border);
        color("magenta")
        translate([border, border, -border])
        linear_extrude(cap.y)
        offset(r = border)
        square(bat.x - border);
        }
}

if (true) {
// "base" shift so we are aligned to (0,0)
translate([border, border, 0])
union() {
    battery_bed();
    // CPU bed shift to batter_bed TOP
    translate([10, border, bat.z + border*2])
    cpu_bed();
    
    // built on top of battery bed
    translate([0, 0, cap_offset + bat.z + border*2])
    union() {
        cpu_cap();
        // sensor tower
        //translate([bat.x, bat.y, 0]/2 + [0, 0, 20])
        //difference() {
        //    tower = [10, 30];
        //    cylinder(tower.y, r=tower.x, center=false);
        //    cylinder(h=tower.y*3, r=6, center=true);
        //}
    }
}
translate([0, 100, 0])
union() {
    difference() {
    cylinder(20, 30, 15);
    translate([0, 0, 10])
    union() {
    grand_cross(4);
    rotate([0, 0, 45])
    grand_cross(4);
    }
    translate([0, 0, -4])
    cylinder(20, 30, 15);
}
}
}

function vec_star_vec(a, b) =
    [a.x * b.x, a.y * b.y, a.z * b.z];

module rounded_box(size, radius){
    height = size.z;
    points = [
    [0,0,0], [1,0,0], [0,1,0], [1,1,0]
    ];
    size = [
    size.x - radius*2,
    size.y - radius*2,
    size.z
    ];
    //scale(size)
    hull(){
        for (p = points){
            translate(vec_star_vec(p, size))
            translate([radius, radius, 0])
            cylinder(r=radius, h=height);
        }
    }
}

translate([0, 0, 80])
difference() {
    s_b = [bat.x+border*3, bat.y+border*3];
    s_t = s_b - [10, 10];
    rounded_thing(s_b, s_t, 10);
    translate([0, 0, -2])
    rounded_thing(s_b, s_t, 10);
    hole_start = (s_b - s_t)/2;
    hole_end = s_t + hole_start/2;
    steps = 10;
    step = (hole_end - hole_start)/steps;
    color("blue", 0.4)
    union() {
    for (i = [0:steps]) {
translate([-25, 1+hole_start.x+i*step.x, 3])
cube([100, 1, 5]);
rotate([0, 0, 90])
translate([0, -70 + 1+hole_start.x+i*step.x, 3])
cube([100, 1, 5]);
}}

}
   // translate([7, 7, 10])
    //cube([13, 13, 1]);
// available volue draw last to ensure no shadowing is happening
//color("red", 0.1)
//cube([30, 30, 15]);

module rounded_thing(bottom, top, height) {
hull() {
rounded_box([bottom.x, bottom.y, 1], 1);
translate([bottom.x - top.x, bottom.y - top.y, 0] / 2 + [0, 0, height] )
rounded_box([top.x, top.y, 1], 1);
}
}
module grand_cross(size) {
    translate([-50, -size/2, 0])
    cube([100, size, size]);
    translate([-size/2, -50, 0])
    cube([size, 100, size]);
}